"""Retención de ICA (Bogotá, bimestral) e ICA autodeclarado bimestral.

Dos cálculos separados:
- `compute_rete_ica`: lo que el agente de retención retuvo a proveedores (Formulario retenciones ICA).
- `compute_ica_bogota`: ICA propio = ingresos gravados × tarifa por mil según actividad,
  menos rete_ica que le practicaron (a favor).

Tarifas Bogotá (Acuerdo 65/2002 y ajustes): expresadas en “por mil”. Se cargan
las 6 actividades más frecuentes; para lo demás cae en 6.9‰ (servicios generales).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO, money


TARIFAS_ICA_BOGOTA_POR_MIL: dict[str, Decimal] = {
    # comercio al por mayor y menor
    "461": Decimal("4.14"),
    "462": Decimal("4.14"),
    "466": Decimal("4.14"),
    "469": Decimal("4.14"),
    "471": Decimal("4.14"),
    "472": Decimal("4.14"),
    # servicios financieros
    "641": Decimal("11.04"),
    # servicios profesionales / consultoría / técnicos
    "691": Decimal("9.66"),
    "692": Decimal("9.66"),
    "702": Decimal("9.66"),
    "711": Decimal("9.66"),
    "749": Decimal("9.66"),
    # industria manufacturera
    "101": Decimal("4.14"),
    "141": Decimal("4.14"),
    # transporte
    "492": Decimal("6.90"),
    "493": Decimal("6.90"),
}
DEFAULT_TARIFA_POR_MIL = Decimal("6.90")


def tarifa_por_mil(activity_code: str | None) -> Decimal:
    if not activity_code:
        return DEFAULT_TARIFA_POR_MIL
    code = str(activity_code).strip()
    return TARIFAS_ICA_BOGOTA_POR_MIL.get(code[:3], DEFAULT_TARIFA_POR_MIL)


@dataclass
class ReteIcaResult:
    amount: Decimal
    invoice_count: int

    def snapshot(self) -> dict[str, Any]:
        return {"total": str(self.amount), "invoice_count": self.invoice_count}


def compute_rete_ica(invoices: Iterable[dict[str, Any]]) -> ReteIcaResult:
    """Sumatoria de `rete_ica` en facturas recibidas del bimestre."""
    total = ZERO
    n = 0
    for inv in invoices:
        if inv.get("direction") != "recibida":
            continue
        v = D(inv.get("rete_ica"))
        if v <= 0:
            continue
        total += v
        n += 1
    return ReteIcaResult(amount=total, invoice_count=n)


@dataclass
class IcaBogotaResult:
    ingresos_gravados: Decimal
    tarifa_por_mil: Decimal
    impuesto: Decimal
    rete_ica_favor: Decimal
    amount: Decimal
    activity_code: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "ingresos_gravados": str(self.ingresos_gravados),
            "tarifa_por_mil": str(self.tarifa_por_mil),
            "impuesto": str(self.impuesto),
            "rete_ica_favor": str(self.rete_ica_favor),
            "amount": str(self.amount),
            "activity_code": self.activity_code,
        }


def compute_ica_bogota(
    invoices: Iterable[dict[str, Any]],
    activity_code: str | None,
) -> IcaBogotaResult:
    """ICA Bogotá bimestral: (ingresos × tarifa_por_mil / 1000) − rete_ica a favor."""
    ingresos = ZERO
    rete_favor = ZERO
    for inv in invoices:
        if inv.get("direction") == "emitida":
            ingresos += D(inv.get("subtotal"))
            rete_favor += D(inv.get("rete_ica"))
    tarifa = tarifa_por_mil(activity_code)
    impuesto = money(ingresos * tarifa / Decimal("1000"))
    amount = impuesto - rete_favor
    if amount < 0:
        amount = ZERO
    return IcaBogotaResult(
        ingresos_gravados=ingresos,
        tarifa_por_mil=tarifa,
        impuesto=impuesto,
        rete_ica_favor=rete_favor,
        amount=amount,
        activity_code=activity_code or "",
    )
