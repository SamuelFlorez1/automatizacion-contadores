"""Utilidades numéricas para el módulo tax."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0.00")
Q2 = Decimal("0.01")


def D(v: Any) -> Decimal:
    if v is None:
        return ZERO
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return ZERO


def money(v: Decimal) -> Decimal:
    return v.quantize(Q2, rounding=ROUND_HALF_UP)
