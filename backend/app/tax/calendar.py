"""Loader + helpers para el calendario tributario DIAN/distrital.

Convierte los rangos `range_start..range_end` en fecha por último dígito NIT
usando interpolación lineal (patrón canónico de la DIAN cuando el decreto no
publica día exacto por dígito).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

CALENDAR_PATH = Path(__file__).parent / "calendar_2026.json"


@lru_cache
def load_calendar() -> dict[str, Any]:
    return json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))


def due_date_for_digit(range_start: str | date, range_end: str | date, last_digit: int) -> date:
    """Fecha exacta interpolando dentro del rango publicado por la DIAN.

    Convención DIAN: dígito 1 = primer día del rango, dígito 0 = último día.
    Se distribuyen 10 dígitos (1..9,0) linealmente entre inicio y fin.
    """
    if not 0 <= last_digit <= 9:
        raise ValueError(f"last_digit debe estar entre 0 y 9, recibido {last_digit}")
    start = date.fromisoformat(range_start) if isinstance(range_start, str) else range_start
    end = date.fromisoformat(range_end) if isinstance(range_end, str) else range_end
    order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    idx = order.index(last_digit)
    total_days = (end - start).days
    offset = round(idx * total_days / 9)
    return start + timedelta(days=offset)


def iva_periods(frequency: str) -> list[dict[str, Any]]:
    cal = load_calendar()
    key = "iva_bimestral" if frequency == "bimestral" else "iva_cuatrimestral"
    return cal[key]["periods"]


def rete_fuente_periods() -> list[dict[str, Any]]:
    return load_calendar()["rete_fuente"]["periods"]


def simple_periods() -> list[dict[str, Any]]:
    return load_calendar()["regimen_simple"]["anticipos_bimestrales"]


def ica_bogota_periods() -> list[dict[str, Any]]:
    return load_calendar()["ica_bogota"]["periods"]
