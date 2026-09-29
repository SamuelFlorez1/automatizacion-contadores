"""Deducibilidad de gastos según reglas colombianas (versión simplificada).

Reglas aplicadas (ver E.T. arts. 107, 771-2, 771-5, 617, 618):
- Debe existir factura electrónica con NIT del proveedor (si falta NIT → no deducible).
- Debe tener CUFE válido o al menos número de factura (documento equivalente).
- Solo gastos y costos (cuentas 5xxx y 6xxx). Cuentas 41xx (ingresos) no aplican.
- Umbral bancarización (art. 771-5): pagos en efectivo por encima de 100 UVT (~5M COP en 2026)
  no son deducibles; aquí no conocemos el medio de pago hasta conciliar, así que solo se marca
  advertencia si el monto es grande (informativa).
- Facturas emitidas: no aplica (son ingresos), se marca `is_deductible=None`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass
class Deductibility:
    is_deductible: bool | None
    reason: str = ""


UVT_2026 = Decimal("49799")  # aprox; se refinará en Fase 4 (tax).
UMBRAL_BANCARIZACION = UVT_2026 * Decimal("100")


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def assess_deductibility(invoice: dict[str, Any], puc_account: str | None) -> Deductibility:
    direction = invoice.get("direction")
    if direction == "emitida":
        return Deductibility(is_deductible=None, reason="")

    if not (puc_account or "").startswith(("5", "6")):
        return Deductibility(False, "Cuenta no es de gasto/costo")

    supplier_nit = (invoice.get("supplier_nit") or "").strip()
    if not supplier_nit:
        return Deductibility(False, "Falta NIT del proveedor")

    invoice_number = (invoice.get("invoice_number") or "").strip()
    if not invoice_number:
        return Deductibility(False, "Falta número de factura")

    total_cop = _to_decimal(invoice.get("total_cop") or invoice.get("total"))
    reason = ""
    if total_cop >= UMBRAL_BANCARIZACION:
        reason = "Monto alto: validar medio de pago (bancarización art. 771-5)"

    return Deductibility(True, reason)
