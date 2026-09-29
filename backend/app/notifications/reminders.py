"""Envío programado de recordatorios de vencimiento (usado por cron n8n).

Estrategia: se dispara una vez al día. Toma todas las obligaciones `pending`
del despacho cuyo `due_date` está exactamente a 5, 2 o 0 días. Manda un WhatsApp
por cliente (un solo mensaje aunque tenga varias obligaciones ese día).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog

from app.agent.tools import _cop, _fmt_date, _kind_label
from app.db.client import get_service_client
from app.notifications.whatsapp import send_text

log = structlog.get_logger()

WINDOWS = (5, 2, 0)  # días antes del vencimiento


def _mensaje(cliente_nombre: str, oblig_por_dia: dict[int, list[dict]]) -> str:
    partes = [f"Hola {cliente_nombre.split()[0]} 👋 recordatorio de obligaciones fiscales:"]
    for delta in sorted(oblig_por_dia):
        etiqueta = "hoy" if delta == 0 else f"en {delta} día{'s' if delta > 1 else ''}"
        for o in oblig_por_dia[delta]:
            partes.append(
                f"• {_kind_label(o['kind'])} {o['period_label']}: "
                f"{_cop(o['amount'])} — vence {_fmt_date(o['due_date'])} ({etiqueta})"
            )
    partes.append("Escríbenos si necesitas ayuda para pagarla o revisar el cálculo.")
    return "\n".join(partes)


def run_reminders(firm_id: str | None = None, *, today: date | None = None) -> dict[str, Any]:
    """Devuelve resumen `{sent: N, skipped: M, details: [...]}`. Idempotencia:
    n8n corre este job una vez al día; si por algo se corre dos veces, sale
    el mismo mensaje al mismo cliente (se puede mitigar con un log si hace falta)."""
    db = get_service_client()
    today = today or date.today()
    fechas_objetivo = {today + timedelta(days=d): d for d in WINDOWS}

    q = (db.table("tax_obligations")
         .select("client_id, firm_id, kind, period_label, due_date, amount")
         .in_("due_date", [d.isoformat() for d in fechas_objetivo])
         .eq("status", "pending"))
    if firm_id:
        q = q.eq("firm_id", firm_id)
    rows = q.execute().data

    if not rows:
        return {"sent": 0, "skipped": 0, "details": []}

    # Agrupar por cliente → {delta_dias: [obligaciones]}
    por_cliente: dict[str, dict[int, list[dict]]] = {}
    for r in rows:
        d = date.fromisoformat(r["due_date"])
        delta = fechas_objetivo[d]
        por_cliente.setdefault(r["client_id"], {}).setdefault(delta, []).append(r)

    clientes = (db.table("clients")
                .select("id, legal_name, phone")
                .in_("id", list(por_cliente))
                .execute().data)
    by_id = {c["id"]: c for c in clientes}

    sent, skipped, details = 0, 0, []
    for cid, groups in por_cliente.items():
        c = by_id.get(cid)
        if not c or not c.get("phone"):
            skipped += 1
            details.append({"client_id": cid, "sent": False, "reason": "sin teléfono"})
            continue
        text = _mensaje(c["legal_name"], groups)
        res = send_text(c["phone"], text)
        if res.get("ok"):
            sent += 1
            details.append({"client_id": cid, "sent": True, "to": res.get("to")})
        else:
            skipped += 1
            details.append({"client_id": cid, "sent": False, "reason": res.get("reason")})
    return {"sent": sent, "skipped": skipped, "details": details}
