"""Dataset para el reporte mensual (estado de resultados + flujo de caja +
top gastos + comparativo mes anterior + obligaciones fiscales del mes).

Funciones puras `build_dataset(...)` que reciben listas ya filtradas para poder
testear sin tocar Supabase. `fetch_and_build(db, ...)` es la capa de
persistencia que arma los rangos y consulta.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO, money


MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def parse_period(period: str) -> tuple[date, date]:
    """`'2026-07'` → (2026-07-01, 2026-07-31)."""
    y, m = period.split("-")
    year, month = int(y), int(m)
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _previous_period(period: str) -> str:
    y, m = period.split("-")
    year, month = int(y), int(m)
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def _is_expense_account(puc: str | None) -> bool:
    """5xxx = gastos operacionales/no operacionales."""
    return bool(puc) and puc.startswith("5")


def _is_cost_account(puc: str | None) -> bool:
    """6xxx = costos de ventas, 7xxx = costos de producción."""
    return bool(puc) and (puc.startswith("6") or puc.startswith("7"))


# --------------------------------------------------------------------- dataclasses
@dataclass
class IncomeStatement:
    ingresos: Decimal
    costos: Decimal
    gastos: Decimal
    utilidad_bruta: Decimal
    utilidad_operacional: Decimal
    iva_generado: Decimal
    iva_descontable: Decimal
    retenciones_practicadas: Decimal
    retenciones_que_nos_hicieron: Decimal
    n_ingresos: int = 0
    n_egresos: int = 0


@dataclass
class CashFlow:
    ingresos_efectivo: Decimal
    egresos_efectivo: Decimal
    neto: Decimal
    n_movimientos: int
    saldo_final: Decimal | None = None


@dataclass
class ExpenseByCategory:
    proveedor: str
    puc_account: str | None
    total: Decimal
    n_facturas: int


@dataclass
class MonthlyDataset:
    client: dict[str, Any]
    period: str
    period_label: str
    period_start: date
    period_end: date
    generated_at: date
    income_statement: IncomeStatement
    cash_flow: CashFlow
    top_expenses: list[ExpenseByCategory]
    previous_income_statement: IncomeStatement | None
    obligations: list[dict[str, Any]]
    narrative: str = ""

    @property
    def variation_utilidad(self) -> Decimal | None:
        if not self.previous_income_statement:
            return None
        prev = self.previous_income_statement.utilidad_operacional
        curr = self.income_statement.utilidad_operacional
        if prev == ZERO:
            return None
        return money((curr - prev) / prev * Decimal("100"))


# --------------------------------------------------------------------- pure builders
def build_income_statement(invoices: Iterable[dict[str, Any]]) -> IncomeStatement:
    ingresos = costos = gastos = ZERO
    iva_gen = iva_desc = ZERO
    ret_practicadas = ret_favor = ZERO
    n_in = n_out = 0
    for inv in invoices:
        subtotal = D(inv.get("subtotal"))
        iva = D(inv.get("iva"))
        rete_f = D(inv.get("rete_fuente"))
        rete_iva = D(inv.get("rete_iva"))
        rete_ica = D(inv.get("rete_ica"))
        if inv.get("direction") == "emitida":
            n_in += 1
            ingresos += subtotal
            iva_gen += iva
            ret_favor += rete_f + rete_iva + rete_ica
        elif inv.get("direction") == "recibida":
            n_out += 1
            puc = inv.get("puc_account")
            if _is_cost_account(puc):
                costos += subtotal
            else:
                gastos += subtotal
            if inv.get("is_deductible") is True:
                iva_desc += iva
            ret_practicadas += rete_f + rete_iva + rete_ica
    utilidad_bruta = ingresos - costos
    utilidad_op = utilidad_bruta - gastos
    return IncomeStatement(
        ingresos=money(ingresos),
        costos=money(costos),
        gastos=money(gastos),
        utilidad_bruta=money(utilidad_bruta),
        utilidad_operacional=money(utilidad_op),
        iva_generado=money(iva_gen),
        iva_descontable=money(iva_desc),
        retenciones_practicadas=money(ret_practicadas),
        retenciones_que_nos_hicieron=money(ret_favor),
        n_ingresos=n_in,
        n_egresos=n_out,
    )


def build_cash_flow(
    movements: Iterable[dict[str, Any]],
    *,
    invoices: Iterable[dict[str, Any]] | None = None,
) -> CashFlow:
    """Prefiere movimientos bancarios. Si no hay, estima desde totales de
    facturas (útil cuando el cliente no subió extracto del mes)."""
    ingresos = egresos = ZERO
    n = 0
    saldo_final: Decimal | None = None
    for mv in movements:
        n += 1
        amt = D(mv.get("amount"))
        if amt >= 0:
            ingresos += amt
        else:
            egresos += -amt
        if mv.get("balance_after") not in (None, ""):
            saldo_final = D(mv["balance_after"])
    if n == 0 and invoices is not None:
        for inv in invoices:
            total = D(inv.get("total_cop") or inv.get("total"))
            if inv.get("direction") == "emitida":
                ingresos += total
            elif inv.get("direction") == "recibida":
                egresos += total
    return CashFlow(
        ingresos_efectivo=money(ingresos),
        egresos_efectivo=money(egresos),
        neto=money(ingresos - egresos),
        n_movimientos=n,
        saldo_final=money(saldo_final) if saldo_final is not None else None,
    )


def build_top_expenses(
    invoices: Iterable[dict[str, Any]], *, limit: int = 10,
) -> list[ExpenseByCategory]:
    agg: dict[str, dict[str, Any]] = {}
    for inv in invoices:
        if inv.get("direction") != "recibida":
            continue
        key = (inv.get("supplier_name") or "Sin identificar").strip() or "Sin identificar"
        row = agg.setdefault(key, {"total": ZERO, "n": 0, "puc": inv.get("puc_account")})
        row["total"] += D(inv.get("total_cop") or inv.get("total"))
        row["n"] += 1
    ordered = sorted(agg.items(), key=lambda kv: kv[1]["total"], reverse=True)[:limit]
    return [
        ExpenseByCategory(
            proveedor=k,
            puc_account=v["puc"],
            total=money(v["total"]),
            n_facturas=v["n"],
        )
        for k, v in ordered
    ]


def build_dataset(
    *,
    client: dict[str, Any],
    period: str,
    invoices: list[dict[str, Any]],
    movements: list[dict[str, Any]] | None = None,
    previous_invoices: list[dict[str, Any]] | None = None,
    obligations: list[dict[str, Any]] | None = None,
    narrative: str = "",
) -> MonthlyDataset:
    start, end = parse_period(period)
    year = start.year
    label = f"{MESES_ES[start.month - 1].capitalize()} {year}"
    income = build_income_statement(invoices)
    cash = build_cash_flow(movements or [], invoices=invoices)
    top = build_top_expenses(invoices)
    prev = build_income_statement(previous_invoices) if previous_invoices is not None else None
    return MonthlyDataset(
        client=client,
        period=period,
        period_label=label,
        period_start=start,
        period_end=end,
        generated_at=date.today(),
        income_statement=income,
        cash_flow=cash,
        top_expenses=top,
        previous_income_statement=prev,
        obligations=obligations or [],
        narrative=narrative,
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


def _fetch_invoices_range(db, firm_id: str, client_id: str, start: date, end: date) -> list[dict[str, Any]]:
    return (
        db.table("invoices")
        .select("id, direction, issue_date, subtotal, iva, ica, rete_fuente, rete_iva, "
                "rete_ica, total, total_cop, currency, puc_account, is_deductible, "
                "supplier_name, supplier_nit, invoice_number")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .gte("issue_date", start.isoformat()).lte("issue_date", end.isoformat())
        .limit(10000).execute().data
    )


def _fetch_movements_range(db, firm_id: str, client_id: str, start: date, end: date) -> list[dict[str, Any]]:
    return (
        db.table("bank_transactions")
        .select("tx_date, amount, description, reference, balance_after")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .gte("tx_date", start.isoformat()).lte("tx_date", end.isoformat())
        .order("tx_date").limit(10000).execute().data
    )


def _fetch_obligations_month(db, firm_id: str, client_id: str, start: date, end: date) -> list[dict[str, Any]]:
    return (
        db.table("tax_obligations")
        .select("kind, period_label, due_date, amount, status")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .gte("due_date", start.isoformat()).lte("due_date", end.isoformat())
        .order("due_date").execute().data
    )


def fetch_and_build(
    db, *, firm_id: str, client_id: str, period: str, narrative: str = "",
) -> MonthlyDataset:
    client = _fetch_client(db, firm_id, client_id)
    start, end = parse_period(period)
    invoices = _fetch_invoices_range(db, firm_id, client_id, start, end)
    movements = _fetch_movements_range(db, firm_id, client_id, start, end)
    obligations = _fetch_obligations_month(db, firm_id, client_id, start, end)
    prev_period = _previous_period(period)
    p_start, p_end = parse_period(prev_period)
    prev_invoices = _fetch_invoices_range(db, firm_id, client_id, p_start, p_end)
    return build_dataset(
        client=client,
        period=period,
        invoices=invoices,
        movements=movements,
        previous_invoices=prev_invoices,
        obligations=obligations,
        narrative=narrative,
    )
