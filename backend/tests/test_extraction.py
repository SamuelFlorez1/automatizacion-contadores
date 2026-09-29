from datetime import date
from decimal import Decimal

import pytest

from app.extraction.schemas import ExtractionError
from app.extraction.validators import (
    cufe_kind,
    dedupe_key,
    nit_dv,
    normalize_nit,
    validate_nit,
)
from app.extraction.xml_ubl import parse_ubl_invoice
from seeds.generators import Invoice, InvoiceLine, Party, build_ubl_xml, synthetic_cufe


def _party(nit: str, name: str) -> Party:
    return Party(nit=nit, dv=nit_dv(nit), name=name)


def _invoice(**kw) -> Invoice:
    number, issue = "FE-001", date(2026, 8, 5)
    sup, cus = _party("901234567", "Proveedor SAS"), _party("800556677", "Cliente SAS")
    defaults = {
        "number": number,
        "cufe": synthetic_cufe(number, issue, sup.nit, 0),
        "issue_date": issue,
        "due_date": date(2026, 9, 4),
        "supplier": sup,
        "customer": cus,
        "lines": [InvoiceLine("Servicio", 2, 1_000_000), InvoiceLine("Otro", 1, 500_000, iva_rate=0.0)],
    }
    return Invoice(**{**defaults, **kw})


# --- NIT ---------------------------------------------------------------
@pytest.mark.parametrize(
    "nit,dv",
    [("860034313", 7), ("899999068", 1), ("800197268", 4), ("900373913", 4)],
)
def test_nit_dv_known_values(nit, dv):
    assert nit_dv(nit) == dv
    assert validate_nit(nit, dv)


def test_nit_wrong_dv_rejected():
    assert not validate_nit("860034313", 8)
    assert not validate_nit("abc", 1)
    assert not validate_nit(None, 1)
    assert not validate_nit("860034313", None)


def test_normalize_nit():
    assert normalize_nit("860.034.313-7") == "860034313"
    assert normalize_nit(" 900123456 ") == "900123456"
    assert normalize_nit("") is None
    assert normalize_nit(None) is None


# --- CUFE / dedupe ----------------------------------------------------
def test_cufe_kinds():
    assert cufe_kind("a" * 96) == "official"
    assert cufe_kind("b" * 64) == "seed"
    assert cufe_kind("xyz") == "invalid"
    assert cufe_kind("a" * 95 + "...") == "invalid"
    assert cufe_kind(None) == "invalid"


def test_dedupe_key_is_content_based():
    assert dedupe_key(b"abc") == dedupe_key(b"abc")
    assert dedupe_key(b"abc") != dedupe_key(b"abd")


# --- Parser UBL --------------------------------------------------------
def test_parse_valid_invoice_roundtrip():
    inv = _invoice()
    r = parse_ubl_invoice(build_ubl_xml(inv))
    assert r.invoice_number == "FE-001"
    assert r.issue_date == date(2026, 8, 5)
    assert r.supplier_nit == "901234567" and r.supplier_dv == nit_dv("901234567")
    assert r.subtotal == Decimal(str(inv.subtotal))
    assert r.iva == Decimal(str(inv.iva))
    assert r.total == Decimal(str(inv.total))
    assert len(r.lines) == 2 and r.lines[1].iva_rate == 0
    assert not [w for w in r.warnings if "no coincide" in w or "inválido" in w]


def test_parse_withholdings_and_usd_fx():
    inv = _invoice(currency="USD", fx_rate_to_cop=4100.5, rete_fuente_rate=0.04, rete_ica_rate=0.00966)
    r = parse_ubl_invoice(build_ubl_xml(inv))
    assert r.currency == "USD"
    assert r.fx_rate_to_cop == Decimal("4100.500000")
    assert r.rete_fuente == Decimal(str(inv.rete_fuente)) > 0
    assert r.rete_ica == Decimal(str(inv.rete_ica)) > 0
    assert r.total == Decimal(str(inv.total))
    assert r.total_cop == (r.total * r.fx_rate_to_cop).quantize(Decimal("0.01"))
    assert not [w for w in r.warnings if "no coincide" in w]


def test_usd_without_fx_warns():
    r = parse_ubl_invoice(build_ubl_xml(_invoice(currency="USD")))
    assert any("tasa de cambio" in w for w in r.warnings)


def test_bad_nit_check_digit_warns():
    xml = build_ubl_xml(_invoice()).replace(b'schemeID="7"', b'schemeID="3"', 1)
    r = parse_ubl_invoice(xml)
    assert any("Dígito de verificación inválido" in w for w in r.warnings)


def test_total_mismatch_warns():
    xml = build_ubl_xml(_invoice())
    tampered = xml.replace(b"<cbc:PayableAmount currencyID=\"COP\">", b"<cbc:PayableAmount currencyID=\"COP\">9")
    assert any("PayableAmount" in w for w in parse_ubl_invoice(tampered).warnings)


@pytest.mark.parametrize(
    "xml,fragment",
    [
        (b"no es xml", "mal formado"),
        (b"<root/>", "no es una factura UBL"),
    ],
)
def test_invalid_documents_raise(xml, fragment):
    with pytest.raises(ExtractionError, match=fragment):
        parse_ubl_invoice(xml)


def test_missing_required_fields_raise():
    xml = build_ubl_xml(_invoice())
    with pytest.raises(ExtractionError, match="IssueDate"):
        parse_ubl_invoice(xml.replace(b"<cbc:IssueDate>2026-08-05</cbc:IssueDate>", b""))
    with pytest.raises(ExtractionError, match="cbc:ID"):
        parse_ubl_invoice(xml.replace(b"<cbc:ID>FE-001</cbc:ID>", b"", 1))
    with pytest.raises(ExtractionError, match="líneas"):
        parse_ubl_invoice(xml.split(b"<cac:InvoiceLine>")[0] + b"</Invoice>")


def test_xxe_is_not_resolved():
    xxe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">&e;</Invoice>'
    with pytest.raises(ExtractionError):
        parse_ubl_invoice(xxe)
