"""Prellenado de Formulario 300 DIAN (IVA) para un período bimestral/cuatrimestral.

El formulario oficial DIAN tiene ~90 casillas. Aquí prellenamos las
principales del cálculo. Reutiliza `compute_iva` (Fase 4) y las columnas
tarifadas por línea de factura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO, money
from app.tax.calendar import iva_periods, load_calendar
from app.tax.iva import IvaResult, compute_iva


@dataclass
class Form300Row:
    casilla: str
    concepto: str
    valor: Decimal


@dataclass
class Form300Dataset:
    client: dict[str, Any]
    period_label: str
    period_start: date
    period_end: date
    due_date: date | None
    frequency: str  # bimestral | cuatrimestral
    iva: IvaResult
    ventas_gravadas: Decimal
    ventas_excluidas: Decimal
    ventas_exportacion: Decimal
    compras_gravadas: Decimal
    casillas: list[Form300Row] = field(default_factory=list)


def _separate_ventas(invoices: Iterable[dict[str, Any]]) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """(gravadas_subtotal, excluidas_subtotal, exportacion_subtotal, compras_gravadas_subtotal)."""
    ventas_grav = ventas_excl = ventas_exp = ZERO
    compras_grav = ZERO
    for inv in invoices:
        sub = D(inv.get("subtotal"))
        iva = D(inv.get("iva"))
        direction = inv.get("direction")
        if direction == "emitida":
            if inv.get("currency") == "USD":
                ventas_exp += sub
            elif iva > 0:
                ventas_grav += sub
            else:
                ventas_excl += sub
        elif direction == "recibida":
            if iva > 0 and inv.get("is_deductible") is True:
                compras_grav += sub
    return (money(ventas_grav), money(ventas_excl), money(ventas_exp), money(compras_grav))


def _find_period(period_label: str, frequency: str) -> dict[str, Any] | None:
    for p in iva_periods(frequency):
        if p["label"] == period_label:
            return p
    return None


def build_form300(
    *,
    client: dict[str, Any],
    period_label: str,
    frequency: str,
    invoices: list[dict[str, Any]],
    due_date: date | None = None,
) -> Form300Dataset:
    ventas_grav, ventas_excl, ventas_exp, compras_grav = _separate_ventas(invoices)
    iva = compute_iva(invoices)

    period_entry = _find_period(period_label, frequency)
    if period_entry:
        start = date.fromisoformat(period_entry["period_start"])
        end = date.fromisoformat(period_entry["period_end"])
    else:
        start = end = date.today()

    # Casillas principales (numeración indicativa Formulario 300 v2023+).
    filas = [
        Form300Row("32", "Ingresos brutos por operaciones gravadas", ventas_grav),
        Form300Row("33", "Ingresos brutos por operaciones excluidas", ventas_excl),
        Form300Row("34", "Ingresos brutos por exportaciones", ventas_exp),
        Form300Row("41", "Total ingresos brutos recibidos durante el período",
                   money(ventas_grav + ventas_excl + ventas_exp)),
        Form300Row("48", "Compras y servicios gravados", compras_grav),
        Form300Row("55", "Impuesto generado por operaciones gravadas", iva.iva_generado),
        Form300Row("64", "Impuesto descontable por operaciones de compra", iva.iva_descontable),
        Form300Row("77", "Retenciones por IVA que le practicaron (a favor)", iva.rete_iva_favor),
        Form300Row("84", "Saldo a pagar por el período fiscal", iva.amount),
        Form300Row("85", "Saldo a favor del período fiscal",
                   money(-iva.saldo) if iva.saldo < 0 else ZERO),
    ]
    return Form300Dataset(
        client=client,
        period_label=period_label,
        period_start=start,
        period_end=end,
        due_date=due_date,
        frequency=frequency,
        iva=iva,
        ventas_gravadas=ventas_grav,
        ventas_excluidas=ventas_excl,
        ventas_exportacion=ventas_exp,
        compras_gravadas=compras_grav,
        casillas=filas,
    )


# --------------------------------------------------------------------- persistencia
def _fetch_client(db, firm_id: str, client_id: str) -> dict[str, Any]:
    rows = (
        db.table("clients")
        .select("id, firm_id, legal_name, trade_name, nit, nit_dv, tax_regime, "
                "iva_frequency, ica_city, default_currency, phone, email, address")
        .eq("id", client_id).eq("firm_id", firm_id).execute().data
    )
    if not rows:
        raise ValueError("Cliente no encontrado")
    return rows[0]


def fetch_and_build(
    db, *, firm_id: str, client_id: str, period_label: str,
) -> Form300Dataset:
    client = _fetch_client(db, firm_id, client_id)
    frequency = client.get("iva_frequency") or "bimestral"
    if frequency not in ("bimestral", "cuatrimestral"):
        raise ValueError(f"Cliente sin frecuencia IVA aplicable ({frequency})")
    period = _find_period(period_label, frequency)
    if not period:
        raise ValueError(f"Período '{period_label}' no encontrado en calendario {frequency}")
    start = date.fromisoformat(period["period_start"])
    end = date.fromisoformat(period["period_end"])

    invoices = (
        db.table("invoices")
        .select("id, direction, issue_date, subtotal, iva, rete_iva, total, total_cop, "
                "currency, puc_account, is_deductible")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .gte("issue_date", start.isoformat()).lte("issue_date", end.isoformat())
        .limit(10000).execute().data
    )

    # Due date desde tax_obligations si ya se generó
    obl = (
        db.table("tax_obligations")
        .select("due_date")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .eq("kind", f"iva_{frequency}")
        .eq("period_label", period_label).limit(1).execute().data
    )
    due = date.fromisoformat(obl[0]["due_date"]) if obl else None

    return build_form300(
        client=client,
        period_label=period_label,
        frequency=frequency,
        invoices=invoices,
        due_date=due,
    )
