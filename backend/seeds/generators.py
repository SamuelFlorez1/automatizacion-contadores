"""Generadores para el seed: NIT DV, UBL 2.1 XML, CSV bancario e imagen factura."""

from __future__ import annotations

import csv
import hashlib
import io
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw, ImageFont


# -----------------------------------------------------------------------------
# NIT dígito de verificación (algoritmo oficial DIAN)
# -----------------------------------------------------------------------------
NIT_WEIGHTS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]


def nit_dv(nit: str) -> int:
    """Calcula el dígito de verificación de un NIT colombiano."""
    digits = [int(c) for c in reversed(nit)]
    total = sum(d * NIT_WEIGHTS[i] for i, d in enumerate(digits))
    r = total % 11
    return 0 if r < 2 else 11 - r


def validate_nit(nit: str, dv: int) -> bool:
    return nit_dv(nit) == dv


# -----------------------------------------------------------------------------
# Modelos de datos para el seed
# -----------------------------------------------------------------------------
@dataclass
class InvoiceLine:
    description: str
    quantity: float
    unit_price: float
    iva_rate: float = 0.19

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    @property
    def iva_amount(self) -> float:
        return round(self.subtotal * self.iva_rate, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.iva_amount, 2)


@dataclass
class Party:
    nit: str
    dv: int
    name: str
    address: str = "Cra 7 # 100 - 20"
    city: str = "Bogotá"


@dataclass
class Invoice:
    number: str
    cufe: str
    issue_date: date
    due_date: date
    supplier: Party
    customer: Party
    currency: str = "COP"
    fx_rate_to_cop: float | None = None
    lines: list[InvoiceLine] = field(default_factory=list)
    rete_fuente_rate: float = 0.0
    rete_ica_rate: float = 0.0
    payment_status: str = "pending"

    @property
    def subtotal(self) -> float:
        return round(sum(l.subtotal for l in self.lines), 2)

    @property
    def iva(self) -> float:
        return round(sum(l.iva_amount for l in self.lines), 2)

    @property
    def rete_fuente(self) -> float:
        return round(self.subtotal * self.rete_fuente_rate, 2)

    @property
    def rete_ica(self) -> float:
        return round(self.subtotal * self.rete_ica_rate, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.iva - self.rete_fuente - self.rete_ica, 2)

    @property
    def total_cop(self) -> float:
        if self.currency == "USD" and self.fx_rate_to_cop:
            return round(self.total * self.fx_rate_to_cop, 2)
        return self.total


# -----------------------------------------------------------------------------
# CUFE sintético (hash sha256 truncado — no es el algoritmo real DIAN)
# -----------------------------------------------------------------------------
def synthetic_cufe(inv_number: str, issue_date: date, supplier_nit: str, total: float) -> str:
    raw = f"{inv_number}|{issue_date.isoformat()}|{supplier_nit}|{total:.2f}|SEED"
    return hashlib.sha256(raw.encode()).hexdigest()


# -----------------------------------------------------------------------------
# UBL 2.1 XML (schema DIAN factura electrónica — subset válido para demo)
# -----------------------------------------------------------------------------
UBL_NSMAP = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
}
CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"


def _el(parent, tag: str, text: str | None = None, **attrs) -> etree._Element:
    e = etree.SubElement(parent, tag, **attrs)
    if text is not None:
        e.text = text
    return e


def build_ubl_xml(inv: Invoice) -> bytes:
    root = etree.Element("Invoice", nsmap=UBL_NSMAP)
    _el(root, CBC + "UBLVersionID", "UBL 2.1")
    _el(root, CBC + "CustomizationID", "10")
    _el(root, CBC + "ProfileID", "DIAN 2.1")
    _el(root, CBC + "ProfileExecutionID", "1")
    _el(root, CBC + "ID", inv.number)
    _el(root, CBC + "UUID", inv.cufe, schemeName="CUFE-SHA384")
    _el(root, CBC + "IssueDate", inv.issue_date.isoformat())
    _el(root, CBC + "IssueTime", "10:00:00-05:00")
    _el(root, CBC + "DueDate", inv.due_date.isoformat())
    _el(root, CBC + "InvoiceTypeCode", "01")
    _el(root, CBC + "DocumentCurrencyCode", inv.currency)
    _el(root, CBC + "LineCountNumeric", str(len(inv.lines)))

    # Supplier
    sup = _el(root, CAC + "AccountingSupplierParty")
    _el(sup, CBC + "AdditionalAccountID", "1")
    party = _el(sup, CAC + "Party")
    pname = _el(party, CAC + "PartyName")
    _el(pname, CBC + "Name", inv.supplier.name)
    ptax = _el(party, CAC + "PartyTaxScheme")
    _el(ptax, CBC + "RegistrationName", inv.supplier.name)
    _el(ptax, CBC + "CompanyID", inv.supplier.nit, schemeID=str(inv.supplier.dv), schemeName="31")
    tscheme = _el(ptax, CAC + "TaxScheme")
    _el(tscheme, CBC + "ID", "01")
    _el(tscheme, CBC + "Name", "IVA")

    # Customer
    cust = _el(root, CAC + "AccountingCustomerParty")
    _el(cust, CBC + "AdditionalAccountID", "1")
    cparty = _el(cust, CAC + "Party")
    cpname = _el(cparty, CAC + "PartyName")
    _el(cpname, CBC + "Name", inv.customer.name)
    cptax = _el(cparty, CAC + "PartyTaxScheme")
    _el(cptax, CBC + "RegistrationName", inv.customer.name)
    _el(cptax, CBC + "CompanyID", inv.customer.nit, schemeID=str(inv.customer.dv), schemeName="31")
    ctscheme = _el(cptax, CAC + "TaxScheme")
    _el(ctscheme, CBC + "ID", "01")
    _el(ctscheme, CBC + "Name", "IVA")

    # Tax total (IVA)
    ttotal = _el(root, CAC + "TaxTotal")
    _el(ttotal, CBC + "TaxAmount", f"{inv.iva:.2f}", currencyID=inv.currency)
    tsub = _el(ttotal, CAC + "TaxSubtotal")
    _el(tsub, CBC + "TaxableAmount", f"{inv.subtotal:.2f}", currencyID=inv.currency)
    _el(tsub, CBC + "TaxAmount", f"{inv.iva:.2f}", currencyID=inv.currency)
    tcat = _el(tsub, CAC + "TaxCategory")
    _el(tcat, CBC + "Percent", "19.00")
    tscheme2 = _el(tcat, CAC + "TaxScheme")
    _el(tscheme2, CBC + "ID", "01")
    _el(tscheme2, CBC + "Name", "IVA")

    # Monetary total
    mtotal = _el(root, CAC + "LegalMonetaryTotal")
    _el(mtotal, CBC + "LineExtensionAmount", f"{inv.subtotal:.2f}", currencyID=inv.currency)
    _el(mtotal, CBC + "TaxExclusiveAmount", f"{inv.subtotal:.2f}", currencyID=inv.currency)
    _el(mtotal, CBC + "TaxInclusiveAmount", f"{inv.subtotal + inv.iva:.2f}", currencyID=inv.currency)
    _el(mtotal, CBC + "AllowanceTotalAmount", "0.00", currencyID=inv.currency)
    _el(mtotal, CBC + "ChargeTotalAmount", "0.00", currencyID=inv.currency)
    _el(mtotal, CBC + "PrepaidAmount", "0.00", currencyID=inv.currency)
    _el(mtotal, CBC + "PayableAmount", f"{inv.total:.2f}", currencyID=inv.currency)

    for i, line in enumerate(inv.lines, start=1):
        li = _el(root, CAC + "InvoiceLine")
        _el(li, CBC + "ID", str(i))
        _el(li, CBC + "InvoicedQuantity", f"{line.quantity:.2f}", unitCode="94")
        _el(li, CBC + "LineExtensionAmount", f"{line.subtotal:.2f}", currencyID=inv.currency)
        ltt = _el(li, CAC + "TaxTotal")
        _el(ltt, CBC + "TaxAmount", f"{line.iva_amount:.2f}", currencyID=inv.currency)
        lts = _el(ltt, CAC + "TaxSubtotal")
        _el(lts, CBC + "TaxableAmount", f"{line.subtotal:.2f}", currencyID=inv.currency)
        _el(lts, CBC + "TaxAmount", f"{line.iva_amount:.2f}", currencyID=inv.currency)
        ltc = _el(lts, CAC + "TaxCategory")
        _el(ltc, CBC + "Percent", f"{line.iva_rate * 100:.2f}")
        ltcs = _el(ltc, CAC + "TaxScheme")
        _el(ltcs, CBC + "ID", "01")
        _el(ltcs, CBC + "Name", "IVA")
        item = _el(li, CAC + "Item")
        _el(item, CBC + "Description", line.description)
        price = _el(li, CAC + "Price")
        _el(price, CBC + "PriceAmount", f"{line.unit_price:.2f}", currencyID=inv.currency)
        _el(price, CBC + "BaseQuantity", f"{line.quantity:.2f}", unitCode="94")

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# -----------------------------------------------------------------------------
# CSV bancario (formato normalizado)
# -----------------------------------------------------------------------------
@dataclass
class BankTx:
    tx_date: date
    description: str
    reference: str
    amount: float
    balance_after: float


def write_bank_csv(path: Path, account_label: str, currency: str, txs: list[BankTx]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# Cuenta", account_label, "Moneda", currency])
        w.writerow(["fecha", "descripcion", "referencia", "valor", "saldo"])
        for t in txs:
            w.writerow([t.tx_date.isoformat(), t.description, t.reference, f"{t.amount:.2f}", f"{t.balance_after:.2f}"])


# -----------------------------------------------------------------------------
# Imagen PNG de factura (para pruebas de Vision — no es un PDF real)
# -----------------------------------------------------------------------------
def render_invoice_png(inv: Invoice, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    W, H = 800, 1100
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    try:
        f_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        f_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        f_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except OSError:
        f_title = ImageFont.load_default()
        f_body = ImageFont.load_default()
        f_small = ImageFont.load_default()

    y = 40
    d.text((40, y), f"FACTURA ELECTRÓNICA DE VENTA", fill="black", font=f_title); y += 30
    d.text((40, y), f"No. {inv.number}", fill="black", font=f_body); y += 20
    d.text((40, y), f"Fecha: {inv.issue_date.isoformat()}   Vence: {inv.due_date.isoformat()}", fill="black", font=f_body); y += 30
    d.line((40, y, W - 40, y), fill="black"); y += 12

    d.text((40, y), f"Emisor:  {inv.supplier.name}", fill="black", font=f_body); y += 18
    d.text((40, y), f"NIT: {inv.supplier.nit}-{inv.supplier.dv}   {inv.supplier.address}", fill="black", font=f_small); y += 24
    d.text((40, y), f"Cliente: {inv.customer.name}", fill="black", font=f_body); y += 18
    d.text((40, y), f"NIT: {inv.customer.nit}-{inv.customer.dv}   {inv.customer.address}", fill="black", font=f_small); y += 28

    d.line((40, y, W - 40, y), fill="black"); y += 10
    d.text((40, y), "Descripción", fill="black", font=f_body)
    d.text((450, y), "Cant", fill="black", font=f_body)
    d.text((520, y), "V. Unit", fill="black", font=f_body)
    d.text((640, y), "Subtotal", fill="black", font=f_body); y += 20
    d.line((40, y, W - 40, y), fill="black"); y += 8
    for line in inv.lines:
        d.text((40, y), line.description[:52], fill="black", font=f_small)
        d.text((450, y), f"{line.quantity:g}", fill="black", font=f_small)
        d.text((520, y), f"{line.unit_price:,.0f}", fill="black", font=f_small)
        d.text((640, y), f"{line.subtotal:,.0f}", fill="black", font=f_small); y += 18
    y += 10
    d.line((40, y, W - 40, y), fill="black"); y += 12
    d.text((500, y), f"Subtotal:  {inv.subtotal:>14,.2f} {inv.currency}", fill="black", font=f_body); y += 18
    d.text((500, y), f"IVA 19%:   {inv.iva:>14,.2f} {inv.currency}", fill="black", font=f_body); y += 18
    if inv.rete_fuente:
        d.text((500, y), f"ReteFuente: {inv.rete_fuente:>13,.2f} {inv.currency}", fill="black", font=f_body); y += 18
    if inv.rete_ica:
        d.text((500, y), f"ReteICA:   {inv.rete_ica:>14,.2f} {inv.currency}", fill="black", font=f_body); y += 18
    d.text((500, y), f"TOTAL:     {inv.total:>14,.2f} {inv.currency}", fill="black", font=f_title); y += 30
    d.text((40, y), f"CUFE: {inv.cufe[:40]}...", fill="gray", font=f_small); y += 14
    d.text((40, y), "Documento generado sintéticamente — demo", fill="gray", font=f_small)

    img.save(path, "PNG")
