"""Tests de clasificación PUC y deducibilidad (offline, con reglas)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.classification.deductibility import assess_deductibility
from app.classification.puc import classify_invoice


def _base_invoice(**overrides):
    inv = {
        "direction": "recibida",
        "supplier_name": "ETB SA",
        "supplier_nit": "899999115",
        "customer_name": "Consultora Andina",
        "customer_nit": "900111222",
        "invoice_number": "FA-1",
        "issue_date": date(2026, 8, 1),
        "subtotal": Decimal("100000"),
        "iva": Decimal("19000"),
        "total": Decimal("119000"),
        "total_cop": Decimal("119000"),
        "currency": "COP",
        "lines": [{"description": "Servicio de telefonía fija"}],
    }
    inv.update(overrides)
    return inv


def test_classify_rules_telefonia_maps_to_513535():
    inv = _base_invoice()
    cls = classify_invoice(inv, force_rules=True)
    assert cls.puc_account == "513535"
    assert cls.source == "rules"


def test_classify_rules_arriendo_maps_to_512010():
    inv = _base_invoice(
        supplier_name="Arrendamientos Bogotá SA",
        lines=[{"description": "Arriendo mensual oficina"}],
    )
    cls = classify_invoice(inv, force_rules=True)
    assert cls.puc_account == "512010"


def test_classify_rules_ingreso_servicios():
    inv = _base_invoice(direction="emitida",
                        lines=[{"description": "Asesoría contable mensual"}])
    cls = classify_invoice(inv, trade="servicios", force_rules=True)
    assert cls.puc_account == "4155"


def test_classify_rules_ingreso_comercio():
    inv = _base_invoice(direction="emitida",
                        lines=[{"description": "Venta al por mayor"}])
    cls = classify_invoice(inv, trade="comercio", force_rules=True)
    assert cls.puc_account == "4135"


def test_classify_rules_fallback_diversos():
    inv = _base_invoice(
        supplier_name="Anónimo",
        lines=[{"description": "Concepto sin categoría clara"}],
    )
    cls = classify_invoice(inv, force_rules=True)
    assert cls.puc_account == "5195"
    assert cls.confidence < 0.5


def test_deductibility_needs_supplier_nit():
    inv = _base_invoice(supplier_nit="")
    assert assess_deductibility(inv, "513535").is_deductible is False


def test_deductibility_only_gastos_or_costos():
    inv = _base_invoice()
    assert assess_deductibility(inv, "4155").is_deductible is False
    assert assess_deductibility(inv, "513535").is_deductible is True


def test_deductibility_none_for_emitida():
    inv = _base_invoice(direction="emitida")
    assert assess_deductibility(inv, "4155").is_deductible is None


def test_deductibility_flags_bankarization_on_large_amount():
    inv = _base_invoice(total_cop=Decimal("6000000"))  # > 100 UVT
    d = assess_deductibility(inv, "513535")
    assert d.is_deductible is True
    assert "bancarización" in d.reason.lower() or "medio de pago" in d.reason.lower()
