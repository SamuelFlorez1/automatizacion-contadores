"""Genera y persiste `tax_obligations` de un cliente cruzando facturas con el
calendario DIAN/distrital.

Diseño:
- `generate_period(...)` es puro: recibe facturas + config cliente + una entrada
  del calendario y devuelve un `PlannedObligation` (tipo + monto + snapshot).
- `generate_and_persist(...)` reúne los períodos que corresponden al cliente
  (según régimen y actividad), llama a `generate_period`, y hace UPSERT en la
  tabla `tax_obligations` con clave `(client_id, kind, period_label)`.

Todos los cálculos son idempotentes: correrlo dos veces no duplica filas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.tax.calendar import (
    due_date_for_digit,
    ica_bogota_periods,
    iva_periods,
    load_calendar,
    rete_fuente_periods,
    simple_periods,
)
from app.tax.iva import compute_iva
from app.tax.rete_fuente import compute_rete_fuente
from app.tax.rete_ica import compute_ica_bogota, compute_rete_ica
from app.tax.simple import compute_simple_bimestral


@dataclass
class PlannedObligation:
    kind: str
    period_label: str
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal
    calculation_snapshot: dict[str, Any]

    def as_row(self, *, firm_id: str, client_id: str) -> dict[str, Any]:
        return {
            "firm_id": firm_id,
            "client_id": client_id,
            "kind": self.kind,
            "period_label": self.period_label,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "due_date": self.due_date.isoformat(),
            "amount": str(self.amount),
            "calculation_snapshot": self.calculation_snapshot,
            "status": "pending",
        }


# --------------------------------------------------------------------- helpers
def _parse_date(v: str | date) -> date:
    return date.fromisoformat(v) if isinstance(v, str) else v


def _filter_period(invoices: Iterable[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    out = []
    for inv in invoices:
        d = inv.get("issue_date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if d and start <= d <= end:
            out.append(inv)
    return out


def _due(period_entry: dict[str, Any], client_nit_last_digit: int) -> date:
    """Un período del calendario trae `due_date` (ICA Bogotá) o `range_*` DIAN."""
    if "due_date" in period_entry:
        return _parse_date(period_entry["due_date"])
    return due_date_for_digit(period_entry["range_start"], period_entry["range_end"], client_nit_last_digit)


# --------------------------------------------------------------------- generation
def generate_all(
    invoices: list[dict[str, Any]],
    *,
    client: dict[str, Any],
    year: int = 2026,
) -> list[PlannedObligation]:
    """Devuelve todas las obligaciones aplicables al cliente para el año."""
    out: list[PlannedObligation] = []
    last_digit = int(str(client["nit"])[-1])
    regime = client["tax_regime"]
    iva_freq = client.get("iva_frequency") or "no_aplica"
    is_agente_retencion = bool(client.get("is_agente_retencion"))
    activity_code = client.get("ica_activity_code")

    # ---- IVA (solo régimen ordinario con frecuencia definida)
    if regime == "ordinario" and iva_freq in ("bimestral", "cuatrimestral"):
        for p in iva_periods(iva_freq):
            start = _parse_date(p["period_start"])
            end = _parse_date(p["period_end"])
            invs = _filter_period(invoices, start, end)
            r = compute_iva(invs)
            out.append(PlannedObligation(
                kind=f"iva_{iva_freq}",
                period_label=p["label"],
                period_start=start,
                period_end=end,
                due_date=_due(p, last_digit),
                amount=r.amount,
                calculation_snapshot=r.snapshot(),
            ))

    # ---- Retención en la fuente (mensual) — solo agentes de retención
    if is_agente_retencion:
        for p in rete_fuente_periods():
            start = _parse_date(p["period_start"])
            end = _parse_date(p["period_end"])
            invs = _filter_period(invoices, start, end)
            r = compute_rete_fuente(invs)
            out.append(PlannedObligation(
                kind="rete_fuente",
                period_label=p["label"],
                period_start=start,
                period_end=end,
                due_date=_due(p, last_digit),
                amount=r.amount,
                calculation_snapshot=r.snapshot(),
            ))

    # ---- ICA Bogotá bimestral (autodeclaración)
    if (client.get("ica_city") or "").lower().startswith("bogot"):
        for p in ica_bogota_periods():
            start = _parse_date(p["period_start"])
            end = _parse_date(p["period_end"])
            invs = _filter_period(invoices, start, end)
            ica_result = compute_ica_bogota(invs, activity_code)
            rete_ica_result = compute_rete_ica(invs) if is_agente_retencion else None
            snap = ica_result.snapshot()
            if rete_ica_result is not None:
                snap["rete_ica_practicada"] = rete_ica_result.snapshot()
            out.append(PlannedObligation(
                kind="ica_bogota",
                period_label=p["label"],
                period_start=start,
                period_end=end,
                due_date=_due(p, last_digit),
                amount=ica_result.amount,
                calculation_snapshot=snap,
            ))

    # ---- Régimen Simple (anticipos bimestrales)
    if regime == "simple":
        for p in simple_periods():
            start = _parse_date(p["period_start"])
            end = _parse_date(p["period_end"])
            invs = _filter_period(invoices, start, end)
            r = compute_simple_bimestral(invs, activity_code, year=year)
            out.append(PlannedObligation(
                kind="simple_bimestral",
                period_label=p["label"],
                period_start=start,
                period_end=end,
                due_date=_due(p, last_digit),
                amount=r.amount,
                calculation_snapshot=r.snapshot(),
            ))

    return out


# --------------------------------------------------------------------- persistence
def _fetch_client(db, firm_id: str, client_id: str) -> dict[str, Any]:
    rows = (
        db.table("clients")
        .select("id, firm_id, nit, tax_regime, iva_frequency, ica_city, ica_activity_code, is_agente_retencion")
        .eq("id", client_id).eq("firm_id", firm_id).execute().data
    )
    if not rows:
        raise ValueError("Cliente no encontrado")
    return rows[0]


def _fetch_invoices(db, firm_id: str, client_id: str, year: int) -> list[dict[str, Any]]:
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    return (
        db.table("invoices")
        .select(
            "id, direction, issue_date, subtotal, iva, ica, rete_fuente, rete_iva, "
            "rete_ica, total, total_cop, currency, puc_account, is_deductible"
        )
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .gte("issue_date", start).lte("issue_date", end)
        .limit(10000).execute().data
    )


def generate_and_persist(
    db,
    *,
    firm_id: str,
    client_id: str,
    year: int = 2026,
    period_label: str | None = None,
) -> list[dict[str, Any]]:
    """Genera obligaciones para todo el año y hace UPSERT.

    Si se pasa `period_label`, se filtra sólo esa obligación (o esa combinación
    kind+period si hay varias con el mismo label).
    """
    client = _fetch_client(db, firm_id, client_id)
    invoices = _fetch_invoices(db, firm_id, client_id, year)
    planned = generate_all(invoices, client=client, year=year)
    if period_label:
        planned = [p for p in planned if p.period_label == period_label]
    if not planned:
        return []
    rows = [p.as_row(firm_id=firm_id, client_id=client_id) for p in planned]
    db.table("tax_obligations").upsert(rows, on_conflict="client_id,kind,period_label").execute()
    return rows
