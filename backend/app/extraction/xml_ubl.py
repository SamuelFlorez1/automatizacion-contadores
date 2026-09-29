"""Parser de factura electrónica DIAN (UBL 2.1) con validación estructural y de coherencia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import etree

from app.extraction.schemas import ExtractedInvoice, ExtractedLine, ExtractionError
from app.extraction.validators import cufe_kind, normalize_nit, validate_nit

NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
TOLERANCE = Decimal("1.00")  # descuadre aceptable por redondeos

# Códigos TaxScheme DIAN para retenciones
WITHHOLDING = {"05": "rete_iva", "06": "rete_fuente", "07": "rete_ica"}


def _parse(xml_bytes: bytes) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(xml_bytes, parser)
    except etree.XMLSyntaxError as e:
        raise ExtractionError(f"XML mal formado: {e}") from e
    if etree.QName(root).localname != "Invoice" or etree.QName(root).namespace != NS["inv"]:
        raise ExtractionError("El XML no es una factura UBL (raíz distinta de Invoice UBL 2.1)")
    return root


def _text(node: etree._Element, path: str) -> str | None:
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _dec(value: str | None, field: str, default: Decimal | None = None) -> Decimal:
    if value is None:
        if default is not None:
            return default
        raise ExtractionError(f"Falta el campo obligatorio {field}")
    try:
        return Decimal(value)
    except InvalidOperation as e:
        raise ExtractionError(f"Valor numérico inválido en {field}: {value!r}") from e


def _date(value: str | None, field: str, required: bool = True) -> date | None:
    if value is None:
        if required:
            raise ExtractionError(f"Falta el campo obligatorio {field}")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ExtractionError(f"Fecha inválida en {field}: {value!r}") from e


def _party(root: etree._Element, tag: str) -> tuple[str | None, int | None, str | None]:
    party = root.find(f"cac:{tag}/cac:Party", NS)
    if party is None:
        raise ExtractionError(f"Falta el bloque {tag}")
    name = _text(party, "cac:PartyTaxScheme/cbc:RegistrationName") or _text(
        party, "cac:PartyName/cbc:Name"
    )
    company = party.find("cac:PartyTaxScheme/cbc:CompanyID", NS)
    nit = normalize_nit(company.text) if company is not None and company.text else None
    dv_raw = company.get("schemeID") if company is not None else None
    dv = int(dv_raw) if dv_raw and dv_raw.isdigit() else None
    return nit, dv, name


def parse_ubl_invoice(xml_bytes: bytes) -> ExtractedInvoice:
    root = _parse(xml_bytes)
    warnings: list[str] = []

    number = _text(root, "cbc:ID")
    if not number:
        raise ExtractionError("Falta el número de factura (cbc:ID)")
    issue_date = _date(_text(root, "cbc:IssueDate"), "IssueDate")
    due_date = _date(_text(root, "cbc:DueDate"), "DueDate", required=False)
    currency = _text(root, "cbc:DocumentCurrencyCode") or "COP"
    if currency not in ("COP", "USD"):
        raise ExtractionError(f"Moneda no soportada: {currency}")
    cufe = _text(root, "cbc:UUID")

    s_nit, s_dv, s_name = _party(root, "AccountingSupplierParty")
    c_nit, c_dv, c_name = _party(root, "AccountingCustomerParty")
    if not s_nit or not c_nit:
        raise ExtractionError("Falta el NIT del emisor o del adquirente")

    fx: Decimal | None = None
    fx_raw = _text(root, "cac:PaymentExchangeRate/cbc:CalculationRate")
    if fx_raw:
        fx = _dec(fx_raw, "CalculationRate")
    elif currency == "USD":
        warnings.append("Factura en USD sin tasa de cambio (PaymentExchangeRate)")

    mt = root.find("cac:LegalMonetaryTotal", NS)
    if mt is None:
        raise ExtractionError("Falta el bloque LegalMonetaryTotal")
    subtotal = _dec(_text(mt, "cbc:LineExtensionAmount"), "LineExtensionAmount")
    payable = _dec(_text(mt, "cbc:PayableAmount"), "PayableAmount")
    inclusive = _dec(_text(mt, "cbc:TaxInclusiveAmount"), "TaxInclusiveAmount", default=subtotal)
    iva = _dec(_text(root, "cac:TaxTotal/cbc:TaxAmount"), "TaxTotal", default=Decimal("0"))

    withholdings = {"rete_iva": Decimal("0"), "rete_fuente": Decimal("0"), "rete_ica": Decimal("0")}
    for wt in root.findall("cac:WithholdingTaxTotal", NS):
        code = _text(wt, "cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme/cbc:ID")
        key = WITHHOLDING.get(code or "")
        amount = _dec(_text(wt, "cbc:TaxAmount"), "WithholdingTaxTotal", default=Decimal("0"))
        if key:
            withholdings[key] += amount
        else:
            warnings.append(f"Retención con código desconocido {code!r} ignorada")

    lines: list[ExtractedLine] = []
    for li in root.findall("cac:InvoiceLine", NS):
        l_sub = _dec(_text(li, "cbc:LineExtensionAmount"), "InvoiceLine/LineExtensionAmount")
        l_iva = _dec(
            _text(li, "cac:TaxTotal/cbc:TaxAmount"), "InvoiceLine/TaxAmount", default=Decimal("0")
        )
        lines.append(
            ExtractedLine(
                description=_text(li, "cac:Item/cbc:Description") or "(sin descripción)",
                quantity=_dec(
                    _text(li, "cbc:InvoicedQuantity"), "InvoicedQuantity", default=Decimal("1")
                ),
                unit_price=_dec(
                    _text(li, "cac:Price/cbc:PriceAmount"), "PriceAmount", default=Decimal("0")
                ),
                subtotal=l_sub,
                iva_rate=_dec(
                    _text(li, "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory/cbc:Percent"),
                    "Percent",
                    default=Decimal("0"),
                ),
                iva_amount=l_iva,
                total=l_sub + l_iva,
            )
        )
    if not lines:
        raise ExtractionError("La factura no tiene líneas (InvoiceLine)")

    # Coherencia: advertencias, no bloquean (el contador decide)
    if abs(sum(ln.subtotal for ln in lines) - subtotal) > TOLERANCE:
        warnings.append("La suma de líneas no coincide con LineExtensionAmount")
    if abs(subtotal + iva - inclusive) > TOLERANCE:
        warnings.append("Subtotal + IVA no coincide con TaxInclusiveAmount")
    if abs(inclusive - sum(withholdings.values()) - payable) > TOLERANCE:
        warnings.append("PayableAmount no coincide con total menos retenciones")
    for label, nit, dv in (("emisor", s_nit, s_dv), ("adquirente", c_nit, c_dv)):
        if dv is None:
            warnings.append(f"NIT del {label} sin dígito de verificación")
        elif not validate_nit(nit, dv):
            warnings.append(f"Dígito de verificación inválido para NIT del {label} ({nit}-{dv})")
    kind = cufe_kind(cufe)
    if kind == "invalid":
        warnings.append("CUFE ausente o con formato inválido")
    elif kind == "seed":
        warnings.append("CUFE sintético (seed), no verificable contra DIAN")

    return ExtractedInvoice(
        invoice_number=number,
        cufe=cufe,
        issue_date=issue_date,  # type: ignore[arg-type]
        due_date=due_date,
        supplier_nit=s_nit,
        supplier_dv=s_dv,
        supplier_name=s_name,
        customer_nit=c_nit,
        customer_dv=c_dv,
        customer_name=c_name,
        currency=currency,  # type: ignore[arg-type]
        fx_rate_to_cop=fx,
        subtotal=subtotal,
        iva=iva,
        rete_fuente=withholdings["rete_fuente"],
        rete_iva=withholdings["rete_iva"],
        rete_ica=withholdings["rete_ica"],
        total=payable,
        lines=lines,
        source="xml",
        confidence=1.0,
        warnings=warnings,
    )
