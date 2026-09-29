"""Clasificación PUC con Haiku 4.5.

Recibe una factura extraída (o su fila en `invoices`) y sugiere:
- `puc_account`: cuenta contable del catálogo (código PUC)
- `confidence`: 0..1
- notas cortas para el contador.

Reglas:
- Facturas recibidas → cuentas 5xxx (gastos) o 6xxx (costo de servicios / mercancías).
- Facturas emitidas → cuentas 41xx (ingresos operacionales) según trade del cliente.
- Solo se consideran cuentas hoja del catálogo (con `parent`) más las de primer nivel
  cuando no hay hoja aplicable.
- Si Anthropic no está configurado, cae a un ruteo por reglas simples (`_rule_based`)
  para que el pipeline funcione offline (seed, tests).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
from anthropic import Anthropic

from app.config import get_settings

log = structlog.get_logger()

PUC_PATH = Path(__file__).resolve().parent.parent / "tax" / "puc.json"


@dataclass
class Classification:
    puc_account: str
    confidence: float
    rationale: str = ""
    source: str = "haiku"  # 'haiku' | 'rules'


# ---------------------------------------------------------------- catálogo
@lru_cache
def _puc() -> dict[str, Any]:
    return json.loads(PUC_PATH.read_text(encoding="utf-8"))


def _accounts_for(direction: str, trade: str = "servicios") -> list[dict]:
    """Subset del PUC candidato para clasificar según dirección y actividad."""
    acc = _puc()["accounts"]
    if direction == "recibida":
        prefixes = ("5", "6")
    else:  # emitida
        prefixes = ("41",)
    out: list[dict] = []
    for a in acc:
        if not a["code"].startswith(prefixes):
            continue
        # Cuenta aplica al trade (si el catálogo lo declara) o es cuenta hija (hereda).
        applies = a.get("applies_to")
        if applies and trade not in applies:
            continue
        out.append(a)
    return out


def _catalog_snippet(direction: str, trade: str) -> str:
    return "\n".join(f"{a['code']} — {a['name']}" for a in _accounts_for(direction, trade))


# ---------------------------------------------------------------- reglas offline
# Mapa de palabras clave → cuenta PUC. Cubre el catálogo de gastos común
# del seed; suficiente para pruebas y para no bloquear ingesta si falla Haiku.
_KEYWORD_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(arriendo|arrendamiento|inmobiliaria|inmobiliar)\b", re.I), "512010"),
    (re.compile(r"\b(codensa|energ[ií]a|luz el[eé]ctrica|enel)\b", re.I),        "513530"),
    (re.compile(r"\b(acueducto|acuavalle|epm agua|agua potable)\b", re.I),        "513525"),
    (re.compile(r"\b(gas natural|vanti|surtigas)\b", re.I),                       "513555"),
    (re.compile(r"\b(etb|movistar|claro|tigo|telef[oó]n)\b", re.I),               "513535"),
    (re.compile(r"\b(internet|fibra|banda ancha)\b", re.I),                       "513560"),
    (re.compile(r"\b(transport|flete|acarre|log[ií]stic)\b", re.I),               "513550"),
    (re.compile(r"\b(aseo|vigilanc|seguridad)\b", re.I),                          "513505"),
    (re.compile(r"\b(papeler[ií]a|[uú]tiles|fotocop|imprenta)\b", re.I),          "519545"),
    (re.compile(r"\b(caf[eé]|cafeter[ií]a|elementos de aseo)\b", re.I),           "519530"),
    (re.compile(r"\b(combustible|gasolina|acpm|dies[eé]l|lubricant)\b", re.I),    "519560"),
    (re.compile(r"\b(honorari|asesor[ií]a jur|abogad|estudio legal)\b", re.I),    "511025"),
    (re.compile(r"\b(auditor|revisor[ií]a)\b", re.I),                             "511010"),
    (re.compile(r"\b(asesor[ií]a financ|contabl|contador)\b", re.I),              "511030"),
    (re.compile(r"\b(asesor[ií]a t[eé]cnica|servicios t[eé]cnicos|consultor)\b", re.I), "511035"),
    (re.compile(r"\b(mantenimient|reparaci[oó]n|repuestos)\b", re.I),             "5145"),
    (re.compile(r"\b(seguro|p[oó]liza)\b", re.I),                                 "5130"),
    (re.compile(r"\b(viaj|hotel|tiquete|hospedaje)\b", re.I),                     "5155"),
    (re.compile(r"\b(gastos? bancari|comisi[oó]n bancar|4x1000|gmf)\b", re.I),    "530505"),
    (re.compile(r"\b(inter[eé]s|financiaci[oó]n)\b", re.I),                       "530525"),
    (re.compile(r"\b(mercanc[ií]|import|wholesale|distribuidor)\b", re.I),        "6135"),
]


def _rule_based(text: str, direction: str, trade: str) -> Classification:
    if direction == "emitida":
        code = "4135" if trade == "comercio" else "4155"
        return Classification(code, 0.6, "Ingreso operacional por actividad del cliente", "rules")
    for pattern, code in _KEYWORD_RULES:
        if pattern.search(text):
            return Classification(code, 0.7, f"Regla: {pattern.pattern}", "rules")
    # Fallback razonable: diversos
    return Classification("5195", 0.3, "Sin regla; queda pendiente de revisión", "rules")


# ---------------------------------------------------------------- Haiku
_SYSTEM_PROMPT = (
    "Eres un asistente contable colombiano experto en el PUC (Decreto 2650 de 1993). "
    "Tu tarea es sugerir la cuenta contable más adecuada para registrar una factura. "
    "Debes elegir SIEMPRE una cuenta del catálogo que se te entrega; no inventes códigos. "
    "Prefiere cuentas hoja (6 dígitos) cuando existan; si ninguna cuadra usa la de 4 dígitos. "
    "Devuelve una única llamada a la herramienta `sugerir_cuenta`."
)

_TOOL = {
    "name": "sugerir_cuenta",
    "description": "Sugerir cuenta PUC para la factura.",
    "input_schema": {
        "type": "object",
        "properties": {
            "puc_account": {"type": "string", "description": "Código PUC exacto del catálogo."},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string", "description": "Justificación breve, máx 120 caracteres."},
        },
        "required": ["puc_account", "confidence"],
    },
}


def _client() -> Anthropic | None:
    key = get_settings().anthropic_api_key
    return Anthropic(api_key=key) if key else None


def _summary_text(inv: dict[str, Any]) -> str:
    """Texto que se le pasa a Haiku para clasificar (compacto para ahorrar tokens)."""
    lines = inv.get("lines") or []
    line_desc = " · ".join(str(l.get("description", ""))[:60] for l in lines[:8])
    return (
        f"Dirección: {inv.get('direction')}\n"
        f"Proveedor/Emisor: {inv.get('supplier_name') or '—'} (NIT {inv.get('supplier_nit') or '—'})\n"
        f"Cliente/Adquirente: {inv.get('customer_name') or '—'}\n"
        f"Factura {inv.get('invoice_number') or '—'} · Fecha {inv.get('issue_date') or '—'}\n"
        f"Subtotal {inv.get('subtotal')} · IVA {inv.get('iva')} · Total {inv.get('total')} {inv.get('currency') or 'COP'}\n"
        f"Detalle líneas: {line_desc or '(sin líneas)'}\n"
    )


def classify_invoice(
    invoice: dict[str, Any],
    *,
    trade: str = "servicios",
    force_rules: bool = False,
) -> Classification:
    """Clasifica una factura. `invoice` es un dict con campos de `invoices` + opcional `lines`."""
    direction = invoice.get("direction") or "recibida"
    text = _summary_text(invoice)

    if force_rules:
        return _rule_based(text, direction, trade)

    client = _client()
    if client is None:
        return _rule_based(text, direction, trade)

    catalog = _catalog_snippet(direction, trade)
    valid_codes = {a["code"] for a in _accounts_for(direction, trade)}

    settings = get_settings()
    try:
        resp = client.messages.create(
            model=settings.model_haiku,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "sugerir_cuenta"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Catálogo permitido (dirección={direction}, actividad={trade}):\n{catalog}\n\n"
                        f"Factura:\n{text}\n\n"
                        "Sugiere la cuenta PUC más apropiada."
                    ),
                }
            ],
        )
    except Exception as e:
        log.warning("haiku_classify_failed", error=str(e))
        return _rule_based(text, direction, trade)

    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "sugerir_cuenta":
            code = str(block.input.get("puc_account", "")).strip()
            if code not in valid_codes:
                log.warning("haiku_returned_invalid_code", code=code)
                return _rule_based(text, direction, trade)
            conf = float(block.input.get("confidence") or 0.5)
            conf = max(0.0, min(1.0, conf))
            return Classification(code, conf, str(block.input.get("rationale", ""))[:200], "haiku")

    return _rule_based(text, direction, trade)


# ---------------------------------------------------------------- utilidades DB
def _fetch_invoice_with_lines(db, invoice_id: str) -> dict[str, Any] | None:
    row = db.table("invoices").select("*").eq("id", invoice_id).execute().data
    if not row:
        return None
    inv = row[0]
    inv["lines"] = (
        db.table("invoice_lines").select("description, quantity, unit_price, subtotal, iva_amount, total")
        .eq("invoice_id", invoice_id).order("line_no").execute().data
    )
    return inv


def _client_trade(db, client_id: str) -> str:
    row = db.table("clients").select("ica_activity_code, legal_name").eq("id", client_id).execute().data
    if not row:
        return "servicios"
    # Heurística: si el CIIU empieza en 4 (comercio), es comercio.
    code = (row[0].get("ica_activity_code") or "").strip()
    if code.startswith("4") and not code.startswith("47") is False:  # 45-47 comercio
        return "comercio"
    return "servicios"


def classify_and_persist(db, invoice_id: str, *, force_rules: bool = False) -> Classification:
    inv = _fetch_invoice_with_lines(db, invoice_id)
    if inv is None:
        raise ValueError(f"invoice {invoice_id} no existe")
    trade = _client_trade(db, inv["client_id"])
    cls = classify_invoice(inv, trade=trade, force_rules=force_rules)

    # Importa aquí para evitar ciclo (deductibility usa puc para reglas puntuales).
    from app.classification.deductibility import assess_deductibility

    deduct = assess_deductibility(inv, cls.puc_account)
    notes = _merge_notes(inv.get("notes"), f"[clasificación:{cls.source}] {cls.rationale}".strip())
    if deduct.reason:
        notes = _merge_notes(notes, f"[deducibilidad] {deduct.reason}")

    db.table("invoices").update(
        {
            "puc_account": cls.puc_account,
            "classification_confidence": round(Decimal(str(cls.confidence)), 3).__str__(),
            "is_deductible": deduct.is_deductible,
            "notes": notes,
        }
    ).eq("id", invoice_id).execute()
    return cls


def _merge_notes(existing: str | None, extra: str) -> str:
    parts = [p.strip() for p in (existing or "").split("\n") if p.strip()]
    if extra and extra not in parts:
        parts.append(extra)
    return "\n".join(parts)
