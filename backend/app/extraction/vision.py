"""Extracción de facturas desde imagen/PDF con Claude Vision (salida estructurada vía tool-use)."""

from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from anthropic import Anthropic

from app.config import get_settings
from app.extraction.schemas import ExtractedInvoice, ExtractedLine, ExtractionError
from app.extraction.validators import cufe_kind, normalize_nit, validate_nit

IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PDF_MIME = "application/pdf"

SYSTEM_PROMPT = """Eres un asistente de un despacho contable colombiano. Recibes una factura \
(imagen o PDF) y debes extraer sus datos con exactitud llamando a la herramienta `registrar_factura`.

Reglas:
- Transcribe solo lo que se ve; si un dato no aparece, omítelo (no lo inventes).
- Fechas en formato AAAA-MM-DD. Montos como números sin separadores de miles ni símbolo \
(en Colombia el punto suele separar miles y la coma los decimales: 1.234.567,89 → 1234567.89).
- NIT: solo dígitos del número base; el dígito de verificación va aparte (900123456-7 → nit=900123456, dv=7).
- Moneda: COP por defecto; USD si la factura lo indica. Si es USD y aparece la TRM/tasa de cambio, inclúyela.
- `total` es el valor final a pagar (después de retenciones si las hay).
- `confidence` (0 a 1) refleja qué tan legible y completa está la factura."""

TOOL = {
    "name": "registrar_factura",
    "description": "Registra los datos estructurados extraídos de la factura.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "cufe": {"type": "string"},
            "issue_date": {"type": "string", "description": "AAAA-MM-DD"},
            "due_date": {"type": "string", "description": "AAAA-MM-DD"},
            "supplier_nit": {"type": "string"},
            "supplier_dv": {"type": "integer"},
            "supplier_name": {"type": "string"},
            "customer_nit": {"type": "string"},
            "customer_dv": {"type": "integer"},
            "customer_name": {"type": "string"},
            "currency": {"type": "string", "enum": ["COP", "USD"]},
            "fx_rate_to_cop": {"type": "number"},
            "subtotal": {"type": "number"},
            "iva": {"type": "number"},
            "rete_fuente": {"type": "number"},
            "rete_iva": {"type": "number"},
            "rete_ica": {"type": "number"},
            "total": {"type": "number"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit_price": {"type": "number"},
                        "subtotal": {"type": "number"},
                        "iva_rate": {"type": "number", "description": "porcentaje, ej. 19"},
                        "iva_amount": {"type": "number"},
                        "total": {"type": "number"},
                    },
                    "required": ["description"],
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["invoice_number", "issue_date", "supplier_nit", "customer_nit", "total"],
    },
}


def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v)) if v is not None else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _build_content(data: bytes, mime: str) -> list[dict[str, Any]]:
    b64 = base64.standard_b64encode(data).decode()
    if mime == PDF_MIME:
        block = {"type": "document", "source": {"type": "base64", "media_type": mime, "data": b64}}
    elif mime in IMAGE_MIMES:
        block = {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}
    else:
        raise ExtractionError(f"Tipo de archivo no soportado para Vision: {mime}")
    return [block, {"type": "text", "text": "Extrae los datos de esta factura."}]


def to_extracted_invoice(raw: dict[str, Any]) -> ExtractedInvoice:
    """Convierte el JSON del modelo en ExtractedInvoice validando lo verificable."""
    warnings = ["Extraído con IA (Vision): revisar antes de declarar"]
    try:
        issue = date.fromisoformat(raw["issue_date"])
        number = str(raw["invoice_number"]).strip()
    except (KeyError, ValueError, TypeError) as e:
        raise ExtractionError(f"Vision no devolvió número/fecha válidos: {e}") from e
    if not number:
        raise ExtractionError("Vision no devolvió número de factura")

    due = None
    if raw.get("due_date"):
        try:
            due = date.fromisoformat(raw["due_date"])
        except ValueError:
            warnings.append("Fecha de vencimiento ilegible")

    s_nit, c_nit = normalize_nit(raw.get("supplier_nit")), normalize_nit(raw.get("customer_nit"))
    if not s_nit or not c_nit:
        raise ExtractionError("Vision no pudo leer el NIT del emisor o del adquirente")
    for label, nit, dv in (
        ("emisor", s_nit, raw.get("supplier_dv")),
        ("adquirente", c_nit, raw.get("customer_dv")),
    ):
        if dv is not None and not validate_nit(nit, dv):
            warnings.append(f"Dígito de verificación inválido para NIT del {label} ({nit}-{dv}); posible error de lectura")

    currency = raw.get("currency") or "COP"
    fx = _dec(raw.get("fx_rate_to_cop")) or None
    if currency == "USD" and not fx:
        warnings.append("Factura en USD sin tasa de cambio")

    lines = [
        ExtractedLine(
            description=ln.get("description") or "(sin descripción)",
            quantity=_dec(ln.get("quantity", 1)),
            unit_price=_dec(ln.get("unit_price")),
            subtotal=_dec(ln.get("subtotal")),
            iva_rate=_dec(ln.get("iva_rate")),
            iva_amount=_dec(ln.get("iva_amount")),
            total=_dec(ln.get("total")),
        )
        for ln in raw.get("lines") or []
    ]
    subtotal, iva, total = _dec(raw.get("subtotal")), _dec(raw.get("iva")), _dec(raw.get("total"))
    rf, ri, rc = _dec(raw.get("rete_fuente")), _dec(raw.get("rete_iva")), _dec(raw.get("rete_ica"))
    if subtotal and abs(subtotal + iva - rf - ri - rc - total) > Decimal("1.00"):
        warnings.append("Subtotal + IVA − retenciones no coincide con el total")

    cufe = (raw.get("cufe") or "").strip().lower() or None
    if cufe and cufe_kind(cufe) == "invalid":
        warnings.append("CUFE ilegible o truncado en el documento; se descartó")
        cufe = None

    return ExtractedInvoice(
        invoice_number=number,
        cufe=cufe,
        issue_date=issue,
        due_date=due,
        supplier_nit=s_nit,
        supplier_dv=raw.get("supplier_dv"),
        supplier_name=raw.get("supplier_name"),
        customer_nit=c_nit,
        customer_dv=raw.get("customer_dv"),
        customer_name=raw.get("customer_name"),
        currency=currency if currency in ("COP", "USD") else "COP",
        fx_rate_to_cop=fx,
        subtotal=subtotal,
        iva=iva,
        rete_fuente=rf,
        rete_iva=ri,
        rete_ica=rc,
        total=total,
        lines=lines,
        source="vision",
        confidence=float(raw["confidence"]) if raw.get("confidence") is not None else 0.5,
        warnings=warnings,
    )


def extract_invoice_vision(data: bytes, mime: str, client: Anthropic | None = None) -> ExtractedInvoice:
    s = get_settings()
    if not s.anthropic_api_key and client is None:
        raise ExtractionError("ANTHROPIC_API_KEY no configurada")
    client = client or Anthropic(api_key=s.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=s.model_sonnet,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]},
            messages=[{"role": "user", "content": _build_content(data, mime)}],
        )
    except ExtractionError:
        raise
    except Exception as e:  # errores de red/API: el documento queda en error, el archivo se conserva
        raise ExtractionError(f"Fallo al llamar a Claude Vision: {e}") from e
    for block in resp.content:
        if block.type == "tool_use" and block.name == TOOL["name"]:
            return to_extracted_invoice(block.input)
    raise ExtractionError("Claude Vision no devolvió datos estructurados")
