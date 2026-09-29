"""Tests de Fase 6 — reportes PDF.

Cubren:
- builder puro `build_dataset` (Estado resultados, flujo caja, top gastos).
- builder puro `build_form300` (casillas y saldo).
- Render HTML+PDF end-to-end (WeasyPrint) — skip si libs de sistema faltan.
- Narrativa determinística sin API key.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest

from app.reports.iva_form300 import build_form300
from app.reports.monthly import (
    build_cash_flow,
    build_dataset,
    build_income_statement,
    build_top_expenses,
    parse_period,
)


CLIENT = {
    "id": "c1", "firm_id": "f1", "legal_name": "Andina S.A.S.", "trade_name": "Andina",
    "nit": "900123456", "nit_dv": 7, "tax_regime": "ordinario",
    "iva_frequency": "bimestral", "ica_city": "Bogotá",
    "default_currency": "COP", "phone": "+573001112233", "email": "a@a.co",
    "address": "Cra 1",
}


def _inv(**kw):
    base = dict(
        direction="emitida", issue_date=date(2026, 7, 15),
        subtotal=0, iva=0, rete_fuente=0, rete_iva=0, rete_ica=0,
        total=0, total_cop=0, currency="COP",
        puc_account=None, is_deductible=None, supplier_name=None,
    )
    base.update(kw)
    return base


# --------------------------------------------------------------- puros
def test_parse_period():
    s, e = parse_period("2026-07")
    assert s == date(2026, 7, 1)
    assert e == date(2026, 7, 31)


def test_income_statement_basico():
    invs = [
        _inv(direction="emitida", subtotal=1_000_000, iva=190_000),
        _inv(direction="recibida", subtotal=300_000, iva=57_000,
             puc_account="5195", is_deductible=True),
        _inv(direction="recibida", subtotal=200_000, iva=38_000,
             puc_account="6135", is_deductible=True),  # 6xxx = costo
    ]
    r = build_income_statement(invs)
    assert r.ingresos == Decimal("1000000.00")
    assert r.costos == Decimal("200000.00")
    assert r.gastos == Decimal("300000.00")
    assert r.utilidad_bruta == Decimal("800000.00")
    assert r.utilidad_operacional == Decimal("500000.00")
    assert r.iva_generado == Decimal("190000.00")
    assert r.iva_descontable == Decimal("95000.00")


def test_income_statement_iva_no_descontable_no_suma():
    invs = [
        _inv(direction="recibida", subtotal=100_000, iva=19_000,
             puc_account="5195", is_deductible=False),
    ]
    r = build_income_statement(invs)
    assert r.iva_descontable == Decimal("0.00")


def test_top_expenses_agrupa_y_ordena():
    invs = [
        _inv(direction="recibida", supplier_name="ETB", total_cop=100_000),
        _inv(direction="recibida", supplier_name="ETB", total_cop=50_000),
        _inv(direction="recibida", supplier_name="Codensa", total_cop=200_000),
        _inv(direction="emitida", supplier_name="Cliente X", total_cop=500_000),  # no cuenta
    ]
    top = build_top_expenses(invs)
    assert [t.proveedor for t in top] == ["Codensa", "ETB"]
    assert top[0].total == Decimal("200000.00")
    assert top[1].total == Decimal("150000.00")
    assert top[1].n_facturas == 2


def test_cash_flow_movimientos_reales():
    mvs = [
        {"amount": 500_000, "balance_after": 500_000},
        {"amount": -200_000, "balance_after": 300_000},
        {"amount": 100_000, "balance_after": 400_000},
    ]
    cf = build_cash_flow(mvs)
    assert cf.ingresos_efectivo == Decimal("600000.00")
    assert cf.egresos_efectivo == Decimal("200000.00")
    assert cf.neto == Decimal("400000.00")
    assert cf.saldo_final == Decimal("400000.00")
    assert cf.n_movimientos == 3


def test_cash_flow_fallback_a_facturas_cuando_no_hay_movimientos():
    invs = [
        _inv(direction="emitida", total_cop=1_000_000),
        _inv(direction="recibida", total_cop=400_000),
    ]
    cf = build_cash_flow([], invoices=invs)
    assert cf.ingresos_efectivo == Decimal("1000000.00")
    assert cf.egresos_efectivo == Decimal("400000.00")
    assert cf.neto == Decimal("600000.00")
    assert cf.n_movimientos == 0


def test_build_dataset_variacion():
    invs = [_inv(direction="emitida", subtotal=1_000_000)]
    prev = [_inv(direction="emitida", subtotal=800_000)]
    ds = build_dataset(client=CLIENT, period="2026-07", invoices=invs,
                       previous_invoices=prev)
    assert ds.income_statement.utilidad_operacional == Decimal("1000000.00")
    assert ds.previous_income_statement.utilidad_operacional == Decimal("800000.00")
    # (1_000_000 - 800_000) / 800_000 * 100 = 25.00
    assert ds.variation_utilidad == Decimal("25.00")


def test_build_dataset_sin_previo_no_calcula_variacion():
    ds = build_dataset(client=CLIENT, period="2026-07", invoices=[])
    assert ds.previous_income_statement is None
    assert ds.variation_utilidad is None


# --------------------------------------------------------------- Form 300
def test_form300_saldo_a_pagar():
    invs = [
        _inv(direction="emitida", subtotal=1_000_000, iva=190_000),
        _inv(direction="recibida", subtotal=300_000, iva=57_000,
             puc_account="5195", is_deductible=True),
    ]
    ds = build_form300(client=CLIENT, period_label="jul-ago-2026",
                       frequency="bimestral", invoices=invs)
    assert ds.iva.iva_generado == Decimal("190000.00")
    assert ds.iva.iva_descontable == Decimal("57000.00")
    assert ds.iva.amount == Decimal("133000.00")
    assert ds.ventas_gravadas == Decimal("1000000.00")
    assert ds.compras_gravadas == Decimal("300000.00")
    # 10 casillas prellenadas
    assert len(ds.casillas) == 10
    casilla_84 = next(c for c in ds.casillas if c.casilla == "84")
    assert casilla_84.valor == Decimal("133000.00")


def test_form300_exportacion_no_es_gravada():
    invs = [
        _inv(direction="emitida", subtotal=500_000, iva=0, currency="USD",
             total_cop=500_000),
    ]
    ds = build_form300(client=CLIENT, period_label="jul-ago-2026",
                       frequency="bimestral", invoices=invs)
    assert ds.ventas_exportacion == Decimal("500000.00")
    assert ds.ventas_gravadas == Decimal("0.00")


# --------------------------------------------------------------- narrative
def test_narrative_fallback_sin_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    # limpia cache de settings
    from app.config import get_settings
    get_settings.cache_clear()

    from app.reports.narrative import generate_narrative

    ds = build_dataset(
        client=CLIENT, period="2026-07",
        invoices=[_inv(direction="emitida", subtotal=1_000_000, iva=190_000)],
    )
    text = generate_narrative(ds)
    assert "Andina" in text
    assert "julio" in text.lower() or "Julio" in text


# --------------------------------------------------------------- render (E2E)
def _weasy_available() -> bool:
    try:
        from weasyprint import HTML  # noqa
        HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _weasy_available(),
                    reason="WeasyPrint no puede cargar libs de sistema (pango/cairo)")
def test_render_monthly_pdf():
    from app.reports.pdf import render_html, html_to_pdf

    invs = [
        _inv(direction="emitida", subtotal=1_000_000, iva=190_000),
        _inv(direction="recibida", subtotal=300_000, iva=57_000,
             puc_account="5195", is_deductible=True, supplier_name="ETB"),
    ]
    ds = build_dataset(client=CLIENT, period="2026-07", invoices=invs)
    ds.narrative = "Resumen ejecutivo de prueba."
    html = render_html("monthly.html", {"ds": ds, "generated_at": "2026-09-28"})
    assert "Andina" in html
    assert "ETB" in html
    pdf = html_to_pdf(html)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


@pytest.mark.skipif(not _weasy_available(),
                    reason="WeasyPrint no puede cargar libs de sistema (pango/cairo)")
def test_render_iva_pdf():
    from app.reports.pdf import render_html, html_to_pdf

    invs = [
        _inv(direction="emitida", subtotal=1_000_000, iva=190_000),
        _inv(direction="recibida", subtotal=300_000, iva=57_000,
             puc_account="5195", is_deductible=True),
    ]
    ds = build_form300(client=CLIENT, period_label="jul-ago-2026",
                       frequency="bimestral", invoices=invs)
    html = render_html("iva_form300.html", {"ds": ds, "generated_at": "2026-09-28"})
    assert "Formulario 300" in html
    assert "$133.000" in html or "133000" in html
    pdf = html_to_pdf(html)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
