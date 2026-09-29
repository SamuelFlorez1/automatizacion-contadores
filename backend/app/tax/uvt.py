"""Unidad de Valor Tributario (UVT) por año — DIAN.

Se centraliza aquí para poder actualizar un solo lugar cuando cambia el UVT.
"""

from __future__ import annotations

from decimal import Decimal

UVT_BY_YEAR: dict[int, Decimal] = {
    2025: Decimal("47065"),
    2026: Decimal("49799"),
}


def uvt(year: int) -> Decimal:
    if year not in UVT_BY_YEAR:
        raise ValueError(f"UVT no cargado para {year}")
    return UVT_BY_YEAR[year]


def to_uvt(cop: Decimal, year: int) -> Decimal:
    return (cop / uvt(year)).quantize(Decimal("0.01"))
