"""Régimen Simple de Tributación (RST) — anticipo bimestral.

Base gravable = ingresos brutos del bimestre (ordinarios y extraordinarios,
sin IVA ni Impuesto al Consumo).

Tarifa consolidada = f(grupo de actividad, rango de ingresos anuales en UVT).
Se usa la tabla vigente 2026 (Ley 2277/2022 art. 44, mod. por Ley 2382/2024).

Grupos:
  1. Tiendas pequeñas, mini-mercados, peluquerías.
  2. Actividades comerciales al por mayor y menor; agrícola.
  3. Servicios profesionales, consultoría, científicos (donde el ingreso deriva
     del factor intelectual sobre el material).
  4. Educación y servicios de atención de la salud.
  5. Actividades de expendio de comidas y bebidas; transporte.

El grupo se determina desde el `ica_activity_code` CIIU registrado al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO, money
from app.tax.uvt import uvt


# CIIU (2 primeros dígitos) → grupo Simple. Sub-set representativo suficiente
# para la demo; en producción se carga la tabla completa DIAN.
CIIU_TO_GRUPO: dict[str, int] = {
    # Grupo 2: comercio y agricultura
    "01": 2, "02": 2, "03": 2,
    "45": 2, "46": 2, "47": 2,
    # Grupo 3: servicios profesionales, consultoría
    "62": 3, "63": 3, "69": 3, "70": 3, "71": 3, "72": 3, "73": 3, "74": 3, "82": 3,
    # Grupo 4: educación y salud
    "85": 4, "86": 4, "87": 4, "88": 4,
    # Grupo 5: comidas, bebidas, transporte
    "49": 5, "50": 5, "51": 5, "52": 5, "55": 5, "56": 5,
}


# Tarifas consolidadas bimestrales por grupo y rango de ingresos brutos anuales
# expresados en UVT. Cada entrada: (uvt_max_inclusive, tarifa_decimal).
# Fuente: art. 908 E.T. mod. Ley 2277/2022; ajustada 2026.
_TARIFAS: dict[int, list[tuple[Decimal, Decimal]]] = {
    1: [
        (Decimal("6000"),  Decimal("0.012")),
        (Decimal("15000"), Decimal("0.024")),
        (Decimal("30000"), Decimal("0.045")),
        (Decimal("100000"), Decimal("0.055")),
    ],
    2: [
        (Decimal("6000"),  Decimal("0.016")),
        (Decimal("15000"), Decimal("0.020")),
        (Decimal("30000"), Decimal("0.035")),
        (Decimal("100000"), Decimal("0.045")),
    ],
    3: [
        (Decimal("6000"),  Decimal("0.078")),
        (Decimal("15000"), Decimal("0.088")),
        (Decimal("30000"), Decimal("0.121")),
        (Decimal("100000"), Decimal("0.145")),
    ],
    4: [
        (Decimal("6000"),  Decimal("0.037")),
        (Decimal("15000"), Decimal("0.050")),
        (Decimal("30000"), Decimal("0.070")),
        (Decimal("100000"), Decimal("0.085")),
    ],
    5: [
        (Decimal("6000"),  Decimal("0.032")),
        (Decimal("15000"), Decimal("0.040")),
        (Decimal("30000"), Decimal("0.050")),
        (Decimal("100000"), Decimal("0.070")),
    ],
}


def grupo_from_ciiu(activity_code: str | None) -> int:
    if not activity_code:
        return 3
    prefix = str(activity_code).strip()[:2]
    return CIIU_TO_GRUPO.get(prefix, 3)


def tarifa_simple(grupo: int, ingresos_anuales_cop: Decimal, year: int = 2026) -> Decimal:
    tramos = _TARIFAS.get(grupo, _TARIFAS[3])
    uvt_ingresos = ingresos_anuales_cop / uvt(year)
    for uvt_max, tarifa in tramos:
        if uvt_ingresos <= uvt_max:
            return tarifa
    return tramos[-1][1]


@dataclass
class SimpleResult:
    ingresos_bimestre: Decimal
    ingresos_anualizados: Decimal
    grupo: int
    tarifa: Decimal
    amount: Decimal
    activity_code: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "ingresos_bimestre": str(self.ingresos_bimestre),
            "ingresos_anualizados": str(self.ingresos_anualizados),
            "grupo": self.grupo,
            "tarifa": str(self.tarifa),
            "amount": str(self.amount),
            "activity_code": self.activity_code,
        }


def compute_simple_bimestral(
    invoices: Iterable[dict[str, Any]],
    activity_code: str | None,
    year: int = 2026,
) -> SimpleResult:
    """Anticipo bimestral RST.

    Se anualiza el ingreso del bimestre (×6) para elegir tramo tarifario; luego
    la tarifa se aplica sobre los ingresos del bimestre.
    """
    ingresos = ZERO
    for inv in invoices:
        if inv.get("direction") == "emitida":
            ingresos += D(inv.get("subtotal"))
    grupo = grupo_from_ciiu(activity_code)
    anualizado = ingresos * Decimal("6")
    tarifa = tarifa_simple(grupo, anualizado, year=year)
    amount = money(ingresos * tarifa)
    return SimpleResult(
        ingresos_bimestre=ingresos,
        ingresos_anualizados=anualizado,
        grupo=grupo,
        tarifa=tarifa,
        amount=amount,
        activity_code=activity_code or "",
    )
