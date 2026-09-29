"""Tests de cálculo fiscal: IVA, rete_fuente, rete/ICA Bogotá, Simple, generador."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.tax.iva import compute_iva
from app.tax.obligations import generate_all
from app.tax.rete_fuente import compute_rete_fuente, concepto_from_puc
from app.tax.rete_ica import compute_ica_bogota, compute_rete_ica, tarifa_por_mil
from app.tax.simple import compute_simple_bimestral, grupo_from_ciiu, tarifa_simple


# ------------------------------------------------------------ IVA
def _inv(**kw):
    base = dict(
        direction="emitida",
        issue_date=date(2026, 7, 15),
        subtotal=0, iva=0, ica=0,
        rete_fuente=0, rete_iva=0, rete_ica=0,
        total=0, total_cop=0, currency="COP",
        puc_account=None, is_deductible=None,
    )
    base.update(kw)
    return base


def test_iva_generado_menos_descontable():
    invs = [
        _inv(direction="emitida", subtotal=1_000_000, iva=190_000),
        _inv(direction="emitida", subtotal=500_000,   iva=95_000),
        _inv(direction="recibida", subtotal=300_000, iva=57_000, is_deductible=True),
        _inv(direction="recibida", subtotal=100_000, iva=19_000, is_deductible=False),  # no descontable
    ]
    r = compute_iva(invs)
    assert r.iva_generado == Decimal("285000")
    assert r.iva_descontable == Decimal("57000")
    assert r.saldo == Decimal("228000")
    assert r.amount == Decimal("228000")


def test_iva_rete_iva_a_favor_reduce_saldo():
    invs = [
        _inv(direction="emitida", iva=100_000, rete_iva=15_000),
        _inv(direction="recibida", iva=20_000, is_deductible=True),
    ]
    r = compute_iva(invs)
    # 100000 - 20000 - 15000 = 65000
    assert r.amount == Decimal("65000")
    assert r.rete_iva_favor == Decimal("15000")


def test_iva_saldo_a_favor_no_negativo():
    invs = [
        _inv(direction="emitida", iva=10_000),
        _inv(direction="recibida", iva=50_000, is_deductible=True),
    ]
    r = compute_iva(invs)
    assert r.saldo == Decimal("-40000")
    assert r.amount == Decimal("0")
    assert Decimal(r.snapshot()["saldo_a_favor"]) == Decimal("40000")


# ------------------------------------------------------------ rete fuente
def test_concepto_from_puc_maps_por_prefijo():
    assert concepto_from_puc("511010") == "honorarios"
    assert concepto_from_puc("514005") == "arrendamientos"
    assert concepto_from_puc("6135") == "compras"
    assert concepto_from_puc(None) == "otros"
    assert concepto_from_puc("9999") == "otros"


def test_rete_fuente_suma_por_concepto():
    invs = [
        _inv(direction="recibida", rete_fuente=99_000, puc_account="511010"),
        _inv(direction="recibida", rete_fuente=45_000, puc_account="514005"),
        _inv(direction="recibida", rete_fuente=30_000, puc_account="511505"),
        _inv(direction="emitida", rete_fuente=1000),  # ignorada
        _inv(direction="recibida", rete_fuente=0),    # ignorada
    ]
    r = compute_rete_fuente(invs)
    assert r.amount == Decimal("174000")
    assert r.by_concepto["honorarios"] == Decimal("99000")
    assert r.by_concepto["arrendamientos"] == Decimal("45000")
    assert r.by_concepto["servicios_tecnicos"] == Decimal("30000")
    assert r.invoice_count == 3


# ------------------------------------------------------------ ICA
def test_tarifa_por_mil_conocidas_y_default():
    assert tarifa_por_mil("466") == Decimal("4.14")   # comercio
    assert tarifa_por_mil("749") == Decimal("9.66")   # consultoría
    assert tarifa_por_mil(None) == Decimal("6.90")     # default
    assert tarifa_por_mil("000") == Decimal("6.90")    # default


def test_ica_bogota_ingresos_por_tarifa_menos_rete_favor():
    invs = [
        _inv(direction="emitida", subtotal=10_000_000, rete_ica=41_400),
        _inv(direction="emitida", subtotal=5_000_000),
        _inv(direction="recibida", subtotal=1_000_000, rete_ica=4_140),  # ignorada
    ]
    r = compute_ica_bogota(invs, activity_code="466")  # 4.14 x mil
    # ingresos 15M × 4.14/1000 = 62_100; menos rete_ica favor 41_400 = 20_700
    assert r.ingresos_gravados == Decimal("15000000")
    assert r.impuesto == Decimal("62100.00")
    assert r.rete_ica_favor == Decimal("41400")
    assert r.amount == Decimal("20700.00")


def test_ica_bogota_amount_no_negativo():
    invs = [_inv(direction="emitida", subtotal=100_000, rete_ica=1_000_000)]
    r = compute_ica_bogota(invs, activity_code="466")
    assert r.amount == Decimal("0.00")


def test_rete_ica_practicada_solo_recibidas():
    invs = [
        _inv(direction="recibida", rete_ica=12_000),
        _inv(direction="recibida", rete_ica=8_000),
        _inv(direction="emitida", rete_ica=99_000),  # ignorada
    ]
    r = compute_rete_ica(invs)
    assert r.amount == Decimal("20000")
    assert r.invoice_count == 2


# ------------------------------------------------------------ Simple
def test_grupo_from_ciiu_conocidos():
    assert grupo_from_ciiu("749") == 3   # consultoría
    assert grupo_from_ciiu("466") == 2   # comercio mayorista
    assert grupo_from_ciiu("861") == 4   # salud
    assert grupo_from_ciiu(None) == 3    # default


def test_tarifa_simple_por_tramo():
    # Grupo 3 (consultoría), pequeño (< 6000 UVT)
    peque = Decimal("100_000_000")  # 100M
    assert tarifa_simple(3, peque, year=2026) == Decimal("0.078")
    # Grupo 2 (comercio), pequeño
    assert tarifa_simple(2, peque, year=2026) == Decimal("0.016")


def test_simple_bimestral_amount():
    # Cliente consultoría (CIIU 749 → grupo 3), ingresos bimestrales 5M COP
    invs = [
        _inv(direction="emitida", subtotal=3_000_000),
        _inv(direction="emitida", subtotal=2_000_000),
        _inv(direction="recibida", subtotal=500_000),  # ignorada
    ]
    r = compute_simple_bimestral(invs, activity_code="749", year=2026)
    assert r.grupo == 3
    assert r.ingresos_bimestre == Decimal("5000000")
    assert r.tarifa == Decimal("0.078")  # anualizado 30M → tramo bajo
    assert r.amount == Decimal("390000.00")


# ------------------------------------------------------------ generador
CLIENT_ORD = {
    "id": "cid-b", "nit": "830987654", "tax_regime": "ordinario",
    "iva_frequency": "bimestral", "ica_city": "Bogotá",
    "ica_activity_code": "466", "is_agente_retencion": True,
}
CLIENT_SIMPLE = {
    "id": "cid-a", "nit": "901234567", "tax_regime": "simple",
    "iva_frequency": "no_aplica", "ica_city": "Bogotá",
    "ica_activity_code": "749", "is_agente_retencion": False,
}


def test_generate_all_ordinario_incluye_iva_rete_e_ica():
    invs = [
        _inv(direction="emitida", issue_date=date(2026, 7, 10), subtotal=1_000_000, iva=190_000),
        _inv(direction="recibida", issue_date=date(2026, 7, 12), iva=50_000, is_deductible=True,
             rete_fuente=25_000, puc_account="511010", rete_ica=8_000),
        _inv(direction="emitida", issue_date=date(2026, 12, 15), subtotal=2_000_000, iva=380_000),
    ]
    obligs = generate_all(invs, client=CLIENT_ORD, year=2026)
    kinds = {o.kind for o in obligs}
    assert "iva_bimestral" in kinds
    assert "rete_fuente" in kinds
    assert "ica_bogota" in kinds
    assert "simple_bimestral" not in kinds
    # 6 IVA + 12 rete + 6 ICA = 24
    assert len(obligs) == 24


def test_generate_all_simple_no_incluye_iva():
    invs = [_inv(direction="emitida", issue_date=date(2026, 3, 10), subtotal=8_000_000)]
    obligs = generate_all(invs, client=CLIENT_SIMPLE, year=2026)
    kinds = {o.kind for o in obligs}
    assert "iva_bimestral" not in kinds
    assert "iva_cuatrimestral" not in kinds
    assert "simple_bimestral" in kinds
    assert "rete_fuente" not in kinds  # no es agente retenedor
    # 6 simple + 6 ica
    assert len(obligs) == 12


def test_generate_all_idempotente_period_label_unico_por_kind():
    invs = []
    obligs = generate_all(invs, client=CLIENT_ORD, year=2026)
    keys = [(o.kind, o.period_label) for o in obligs]
    assert len(keys) == len(set(keys)), "cada (kind, period_label) debe ser único"


def test_generate_all_amount_es_cero_sin_facturas():
    obligs = generate_all([], client=CLIENT_ORD, year=2026)
    assert all(o.amount == Decimal("0") or o.amount == Decimal("0.00") for o in obligs)


def test_generate_all_due_date_dentro_del_rango():
    obligs = generate_all([], client=CLIENT_ORD, year=2026)
    # IVA jul-ago-2026 rango publicado: 2026-09-09..2026-09-22.
    iva_ja = next(o for o in obligs if o.kind == "iva_bimestral" and o.period_label == "jul-ago-2026")
    assert date(2026, 9, 9) <= iva_ja.due_date <= date(2026, 9, 22)
    # NIT último dígito 4 → índice 3 en orden [1..9,0] → aprox 4-5 días desde inicio.
    assert iva_ja.due_date == date(2026, 9, 13)
