"""Herramientas que el agente WhatsApp puede llamar contra la base del despacho.

Cada `execute_*` recibe un `client` (dict con id/firm_id/etc.) y devuelve un dict
serializable a JSON. Los formateadores devuelven strings cortos listos para pegar
en la respuesta al usuario (COP con separador de miles, fechas 'dd MMM').

Diseño:
- Las tools son puras respecto al contexto del cliente: nunca cruzan a otro cliente.
- Toda respuesta cabe en un mensaje WhatsApp (~500 caracteres). Si hay más, se resume.
- Errores → se devuelven como texto explicativo (nunca stack traces). El loop puede
  reintentar o escalar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import structlog
from supabase import Client

log = structlog.get_logger()


# --------------------------------------------------------------- schemas Anthropic
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_pending_invoices",
        "description": (
            "Lista las facturas del cliente que están pendientes de procesamiento "
            "(status='error', 'parsing' o sin clasificar). Útil cuando el usuario "
            "pregunta '¿qué facturas me faltan?' o '¿hay algo pendiente?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
            },
        },
    },
    {
        "name": "get_tax_obligations",
        "description": (
            "Devuelve las obligaciones fiscales del cliente (IVA, rete-fuente, ICA, Simple) "
            "próximas a vencer o vencidas. Úsala cuando el usuario pregunta por impuestos, "
            "vencimientos, cuánto debe pagar o cuándo vence algo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "overdue", "all"],
                    "default": "pending",
                    "description": "Filtro de estado. 'pending' incluye vencidas y por vencer.",
                },
                "days_ahead": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 90,
                    "default": 30,
                    "description": "Ventana de días hacia adelante desde hoy.",
                },
            },
        },
    },
    {
        "name": "get_missing_documents",
        "description": (
            "Revisa qué meses del año no tienen facturas registradas para el cliente. "
            "Útil cuando se sospecha que falta información contable de un período."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 2020, "maximum": 2030, "default": 2026},
            },
        },
    },
    {
        "name": "search_document",
        "description": (
            "Busca una factura por número, NIT del proveedor o nombre del proveedor. "
            "Devuelve hasta 5 coincidencias con datos clave."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2, "description": "Texto a buscar (número, NIT o nombre)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escala la conversación a un contador humano cuando el usuario pide hablar con "
            "una persona, cuando la duda es fiscal compleja (interpretación de norma, plan "
            "tributario, requerimiento DIAN) o cuando el agente no tiene información suficiente. "
            "Marca la conversación como 'escalated' y responde al usuario que un contador "
            "le escribirá pronto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Motivo breve del escalamiento."},
            },
            "required": ["reason"],
        },
    },
]


# --------------------------------------------------------------- helpers formato
def _cop(n: float | int | str | None) -> str:
    if n in (None, ""):
        return "$0"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return f"${n}"
    return f"${int(round(v)):,}".replace(",", ".")


def _fmt_date(d: str | date | None) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return d
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{d.day:02d} {meses[d.month - 1]} {d.year}"


def _kind_label(kind: str) -> str:
    return {
        "iva_bimestral": "IVA bimestral",
        "iva_cuatrimestral": "IVA cuatrimestral",
        "rete_fuente": "Rete-fuente",
        "rete_iva": "Rete-IVA",
        "rete_ica": "Rete-ICA",
        "ica_bogota": "ICA Bogotá",
        "simple_bimestral": "Régimen Simple",
        "simple_anual": "Simple anual",
    }.get(kind, kind)


# --------------------------------------------------------------- resultado
@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any]
    summary: str  # texto plano que el agente puede citar

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "summary": self.summary, **self.data}


# --------------------------------------------------------------- ejecutores
def execute_get_pending_invoices(db: Client, client: dict, args: dict) -> ToolResult:
    limit = int(args.get("limit", 10))
    rows = (
        db.table("documents")
        .select("id, original_name, status, error_detail, received_at, kind")
        .eq("client_id", client["id"])
        .in_("status", ["error", "parsing", "received"])
        .order("received_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    unclassified = (
        db.table("invoices")
        .select("id, invoice_number, supplier_name, total_cop, issue_date")
        .eq("client_id", client["id"])
        .is_("puc_account", "null")
        .order("issue_date", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    total_pend = len(rows)
    total_uncls = len(unclassified)
    if total_pend == 0 and total_uncls == 0:
        return ToolResult(True, {"documents": [], "invoices": []},
                          "Sin documentos pendientes ni facturas por clasificar.")
    lines: list[str] = []
    if total_pend:
        lines.append(f"{total_pend} documento(s) con problema:")
        for d in rows[:5]:
            reason = (d.get("error_detail") or d.get("status") or "")[:60]
            lines.append(f"• {d.get('original_name') or d['id']} — {reason}")
    if total_uncls:
        lines.append(f"{total_uncls} factura(s) sin clasificar (top 5):")
        for i in unclassified[:5]:
            lines.append(
                f"• #{i.get('invoice_number', '?')} {i.get('supplier_name', '')} "
                f"— {_cop(i.get('total_cop'))} ({_fmt_date(i.get('issue_date'))})"
            )
    return ToolResult(True, {"documents": rows, "invoices": unclassified}, "\n".join(lines))


def execute_get_tax_obligations(db: Client, client: dict, args: dict) -> ToolResult:
    status = args.get("status", "pending")
    days_ahead = int(args.get("days_ahead", 30))
    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    q = (
        db.table("tax_obligations")
        .select("kind, period_label, due_date, amount, status")
        .eq("client_id", client["id"])
        .order("due_date")
    )
    if status == "pending":
        q = q.in_("status", ["pending", "overdue"]).lte("due_date", horizon.isoformat())
    elif status == "overdue":
        q = q.eq("status", "overdue")
    rows = q.execute().data

    if not rows:
        return ToolResult(True, {"obligations": []},
                          f"Sin obligaciones {status} en los próximos {days_ahead} días.")
    lines = [f"{len(rows)} obligación(es):"]
    total = 0.0
    for o in rows[:8]:
        d = date.fromisoformat(o["due_date"])
        delta = (d - today).days
        estado = "VENCIDA" if delta < 0 else f"en {delta}d" if delta > 0 else "HOY"
        lines.append(
            f"• {_kind_label(o['kind'])} {o['period_label']}: "
            f"{_cop(o['amount'])} — vence {_fmt_date(d)} ({estado})"
        )
        try:
            total += float(o["amount"])
        except (TypeError, ValueError):
            pass
    lines.append(f"Total: {_cop(total)}")
    return ToolResult(True, {"obligations": rows}, "\n".join(lines))


def execute_get_missing_documents(db: Client, client: dict, args: dict) -> ToolResult:
    year = int(args.get("year", date.today().year))
    rows = (
        db.table("invoices")
        .select("issue_date, direction")
        .eq("client_id", client["id"])
        .gte("issue_date", f"{year}-01-01")
        .lte("issue_date", f"{year}-12-31")
        .execute()
        .data
    )
    counts_recv = [0] * 12
    counts_emit = [0] * 12
    for r in rows:
        try:
            m = date.fromisoformat(r["issue_date"][:10]).month - 1
        except (TypeError, ValueError, KeyError):
            continue
        if r.get("direction") == "recibida":
            counts_recv[m] += 1
        else:
            counts_emit[m] += 1

    today = date.today()
    ultimo_mes = today.month if today.year == year else 12
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    faltantes = []
    for i in range(ultimo_mes):
        if counts_recv[i] == 0 and counts_emit[i] == 0:
            faltantes.append(meses[i])

    if not faltantes:
        summary = f"Todos los meses de {year} tienen facturas registradas."
    else:
        summary = f"Meses de {year} sin facturas: {', '.join(faltantes)}"
    return ToolResult(True, {"received_by_month": counts_recv, "issued_by_month": counts_emit,
                             "missing_months": faltantes, "year": year}, summary)


def execute_search_document(db: Client, client: dict, args: dict) -> ToolResult:
    query = (args.get("query") or "").strip()
    if len(query) < 2:
        return ToolResult(False, {"invoices": []}, "La búsqueda necesita al menos 2 caracteres.")
    q = db.table("invoices").select(
        "id, invoice_number, supplier_name, supplier_nit, issue_date, total_cop, direction"
    ).eq("client_id", client["id"])

    if query.replace("-", "").replace(" ", "").isdigit():
        digits = "".join(c for c in query if c.isdigit())
        rows = q.or_(f"invoice_number.ilike.%{query}%,supplier_nit.ilike.%{digits}%").limit(5).execute().data
    else:
        rows = q.or_(f"supplier_name.ilike.%{query}%,invoice_number.ilike.%{query}%").limit(5).execute().data

    if not rows:
        return ToolResult(True, {"invoices": []}, f"Sin resultados para '{query}'.")
    lines = [f"{len(rows)} resultado(s):"]
    for i in rows:
        lines.append(
            f"• #{i.get('invoice_number', '?')} {i.get('supplier_name', '')} "
            f"({i.get('direction', '')}) — {_cop(i.get('total_cop'))} "
            f"— {_fmt_date(i.get('issue_date'))}"
        )
    return ToolResult(True, {"invoices": rows}, "\n".join(lines))


def execute_escalate_to_human(db: Client, client: dict, args: dict, conversation_id: str) -> ToolResult:
    reason = (args.get("reason") or "")[:200]
    try:
        db.table("conversations").update({"status": "escalated"}).eq("id", conversation_id).execute()
    except Exception as e:
        log.warning("escalate_update_failed", error=str(e), conversation_id=conversation_id)
    summary = (
        "Escalamiento registrado. Un contador del despacho revisará tu caso y te "
        "escribirá durante el próximo día hábil."
    )
    return ToolResult(True, {"escalated": True, "reason": reason}, summary)


# --------------------------------------------------------------- dispatcher
def execute_tool(
    name: str, args: dict, *, db: Client, client: dict, conversation_id: str,
) -> ToolResult:
    try:
        if name == "get_pending_invoices":
            return execute_get_pending_invoices(db, client, args)
        if name == "get_tax_obligations":
            return execute_get_tax_obligations(db, client, args)
        if name == "get_missing_documents":
            return execute_get_missing_documents(db, client, args)
        if name == "search_document":
            return execute_search_document(db, client, args)
        if name == "escalate_to_human":
            return execute_escalate_to_human(db, client, args, conversation_id=conversation_id)
    except Exception as e:
        log.exception("tool_execution_failed", tool=name)
        return ToolResult(False, {"error": str(e)}, f"No pude ejecutar {name}: {e}")
    return ToolResult(False, {}, f"Herramienta desconocida: {name}")
