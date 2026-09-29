"""Tests del motor de conciliación y del parser de CSV bancario."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.reconciliation.csv_parser import CsvParseError, parse_bank_csv
from app.reconciliation.engine import reconcile


# --------------------------------------------------------------- CSV parser
SEEDS = Path(__file__).resolve().parent.parent / "seeds" / "bank_statements"


def test_csv_parser_seed_cop():
    content = (SEEDS / "consultora_andina_bancolombia_2026Q3.csv").read_bytes()
    stmt = parse_bank_csv(content)
    assert stmt.account.currency == "COP"
    assert "Bancolombia" in stmt.account.bank_name
    assert "****3421" in stmt.account.account_number_masked
    # SALDO INICIAL se ignora, retiros y abonos entran
    assert len(stmt.txns) > 5
    # Un pago debitado tiene monto negativo
    debits = [t for t in stmt.txns if t.amount < 0]
    assert debits
    # dedupe_key es único por fila
    assert len({t.dedupe_key for t in stmt.txns}) == len(stmt.txns)


def test_csv_parser_seed_usd():
    content = (SEEDS / "compacifico_bancolombia_usd_2026Q3.csv").read_bytes()
    stmt = parse_bank_csv(content)
    assert stmt.account.currency == "USD"
    for t in stmt.txns:
        assert t.currency == "USD"


def test_csv_parser_rejects_missing_columns():
    bad = b"foo,bar\n1,2\n"
    with pytest.raises(CsvParseError):
        parse_bank_csv(bad)


def test_csv_parser_amount_formats():
    content = (
        b"# Cuenta,Banco X ****1111,Moneda,COP\n"
        b"fecha,descripcion,referencia,valor,saldo\n"
        b"01/07/2026,PAGO PRUEBA,REF1,\"-1.234.567,89\",5000000\n"
        b"02/07/2026,ABONO PRUEBA,REF2,\"(500)\",4999500\n"
    )
    stmt = parse_bank_csv(content)
    assert stmt.txns[0].amount == Decimal("-1234567.89")
    assert stmt.txns[0].tx_date == date(2026, 7, 1)
    assert stmt.txns[1].amount == Decimal("-500")


# --------------------------------------------------------------- engine
def _tx(id_: str, date_: date, amount: str, desc: str, ref: str | None = None, account: str = "acc1"):
    return {
        "id": id_, "bank_account_id": account, "tx_date": date_,
        "description": desc, "reference": ref, "amount": Decimal(amount), "currency": "COP",
    }


def _inv(id_: str, date_: date, total: str, supplier: str, number: str,
         cufe: str | None = None, direction: str = "recibida"):
    return {
        "id": id_, "invoice_number": number, "cufe": cufe, "direction": direction,
        "supplier_name": supplier, "supplier_nit": "900123456",
        "issue_date": date_, "total": Decimal(total), "total_cop": Decimal(total),
        "currency": "COP", "payment_status": "pending",
    }


def test_exact_match_by_reference():
    txns = [_tx("t1", date(2026, 8, 1), "-1500000", "PAGO A ETB", "FCA-R-202608-001")]
    invs = [_inv("i1", date(2026, 7, 30), "1500000", "ETB SA", "FCA-R-202608-001")]
    matches, status, summary = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].match_type == "exact"
    assert matches[0].confidence == 1.0
    assert status["t1"] == "matched"
    assert summary.exact == 1


def test_exact_match_by_amount_and_supplier():
    # Sin referencia bancaria: el motor debe emparejar por monto+nombre proveedor único.
    txns = [_tx("t1", date(2026, 8, 5), "-864000", "PAGO A Estudio Legal & Asociados")]
    invs = [_inv("i1", date(2026, 8, 3), "864000", "Estudio Legal & Asociados", "FCA-R-202608-010")]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].match_type == "exact"
    assert status["t1"] == "matched"


def test_ambiguous_same_amount_yields_no_exact():
    # Dos facturas del mismo monto con distinto proveedor → elige la del proveedor A por similaridad.
    txns = [_tx("t1", date(2026, 8, 5), "-100000", "PAGO A Proveedor A")]
    invs = [
        _inv("i1", date(2026, 8, 3), "100000", "Proveedor A SAS", "FA-001"),
        _inv("i2", date(2026, 8, 4), "100000", "Proveedor B Ltda", "FB-002"),
    ]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].invoice_id == "i1"


def test_recurring_supplier_prefers_closest_date():
    # Dos facturas iguales del mismo proveedor: elige la más cercana en fecha.
    txns = [_tx("t1", date(2026, 8, 10), "-500000", "PAGO A Proveedor X")]
    invs = [
        _inv("i1", date(2026, 7, 1),  "500000", "Proveedor X SAS", "FX-001"),
        _inv("i2", date(2026, 8, 8),  "500000", "Proveedor X SAS", "FX-002"),
    ]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].invoice_id == "i2"
    assert matches[0].match_type == "fuzzy"  # ambigüedad → confianza menor
    assert status["t1"] == "review"


def test_fuzzy_match_amount_tolerance():
    txns = [_tx("t1", date(2026, 8, 6), "-1010000", "PAGO A Codensa SA ESP")]  # 1% arriba
    invs = [_inv("i1", date(2026, 8, 5), "1000000", "Codensa SA ESP", "FA-777")]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].match_type == "fuzzy"
    assert 0.6 <= matches[0].confidence <= 0.9
    assert status["t1"] == "review"


def test_unmatched_atm_withdrawal():
    txns = [_tx("t1", date(2026, 8, 6), "-82000", "RETIRO ATM CB07")]
    invs = [_inv("i1", date(2026, 8, 5), "82000", "Alguien", "FA-1")]
    matches, status, summary = reconcile(txns, invs)
    # ATM sin referencia no debe casar con ninguna factura
    assert not matches
    assert status["t1"] == "unmatched"
    assert summary.unmatched == 1


def test_internal_transfer():
    txns = [
        _tx("t1", date(2026, 8, 10), "-2000000", "TRASLADO ENTRE CUENTAS", account="acc1"),
        _tx("t2", date(2026, 8, 10), "2000000", "TRASLADO ENTRE CUENTAS", account="acc2"),
    ]
    matches, status, summary = reconcile(txns, [])
    assert len(matches) == 2
    assert all(m.match_type == "transfer_internal" for m in matches)
    assert status["t1"] == "matched" and status["t2"] == "matched"
    assert summary.transfer == 2


def test_paid_invoices_are_ignored():
    txns = [_tx("t1", date(2026, 8, 5), "-100000", "PAGO A Foo", "F-1")]
    invs = [_inv("i1", date(2026, 8, 3), "100000", "Foo SAS", "F-1")]
    invs[0]["payment_status"] = "paid"
    matches, status, _ = reconcile(txns, invs)
    assert not matches
    assert status["t1"] == "unmatched"


def test_exact_by_reference_tolerates_retenciones():
    # Factura de $1.000.000; el banco paga $890.000 tras retenciones (11%).
    txns = [_tx("t1", date(2026, 8, 1), "-890000", "PAGO A Proveedor X", "FA-777")]
    invs = [_inv("i1", date(2026, 7, 30), "1000000", "Proveedor X SAS", "FA-777")]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].match_type == "exact"
    assert matches[0].confidence < 1.0  # se penaliza por diferencia
    assert status["t1"] == "matched"


def test_exact_by_reference_but_amount_way_off_becomes_fuzzy():
    # Referencia acierta pero monto difiere 50% → sospechoso, cae a fuzzy.
    txns = [_tx("t1", date(2026, 8, 1), "-500000", "PAGO PARCIAL", "FA-777")]
    invs = [_inv("i1", date(2026, 7, 30), "1000000", "Proveedor X SAS", "FA-777")]
    matches, status, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].match_type == "fuzzy"
    assert status["t1"] == "review"


def test_invoice_used_only_once():
    # Una factura no puede casar dos transacciones.
    txns = [
        _tx("t1", date(2026, 8, 5), "-500000", "PAGO A Foo SAS", "F-9"),
        _tx("t2", date(2026, 8, 6), "-500000", "PAGO A Foo SAS", "F-9"),
    ]
    invs = [_inv("i1", date(2026, 8, 3), "500000", "Foo SAS", "F-9")]
    matches, _, _ = reconcile(txns, invs)
    assert len(matches) == 1
    assert matches[0].bank_transaction_id == "t1"
