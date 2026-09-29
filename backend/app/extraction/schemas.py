"""Modelo común de salida de extracción (XML UBL y Claude Vision)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ExtractionError(Exception):
    """El documento no se pudo interpretar; el mensaje va a documents.error_detail."""


class ExtractedLine(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")
    iva_rate: Decimal = Decimal("0")  # porcentaje, ej. 19
    iva_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class ExtractedInvoice(BaseModel):
    invoice_number: str
    cufe: str | None = None
    issue_date: date
    due_date: date | None = None
    supplier_nit: str | None = None
    supplier_dv: int | None = None
    supplier_name: str | None = None
    customer_nit: str | None = None
    customer_dv: int | None = None
    customer_name: str | None = None
    currency: Literal["COP", "USD"] = "COP"
    fx_rate_to_cop: Decimal | None = None
    subtotal: Decimal = Decimal("0")
    iva: Decimal = Decimal("0")
    rete_fuente: Decimal = Decimal("0")
    rete_iva: Decimal = Decimal("0")
    rete_ica: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    lines: list[ExtractedLine] = Field(default_factory=list)
    source: Literal["xml", "vision"] = "xml"
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)

    @property
    def total_cop(self) -> Decimal:
        if self.currency == "USD" and self.fx_rate_to_cop:
            return (self.total * self.fx_rate_to_cop).quantize(Decimal("0.01"))
        return self.total
