"""Cálculo de IVA bimestral / cuatrimestral (Formulario 300).

Regla resumida (E.T. arts. 420–498):
    IVA a pagar = IVA generado (ventas)
                − IVA descontable (compras deducibles del período)
                − Rete IVA que nos practicaron (a favor)

Notas de simplificación demo:
- Solo se cuentan como descontable las facturas `recibidas` marcadas `is_deductible=True`
  y cuya `puc_account` sea de gasto/costo (5xxx / 6xxx) o inventario/activo relacionado.
  Aquí basta con `is_deductible=True`: la deducibilidad ya evaluó la regla PUC.
- `rete_iva` en `invoices.direction='emitida'` = lo que el comprador nos retuvo → a favor.
- Si el resultado es negativo se retorna 0 en `amount` y el excedente queda en
  `snapshot.saldo_a_favor`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO


@dataclass
class IvaResult:
    iva_generado: Decimal
    iva_descontable: Decimal
    rete_iva_favor: Decimal
    saldo: Decimal          # puede ser negativo (saldo a favor)
    amount: Decimal         # 0 si saldo < 0
    invoices_emitidas: int
    invoices_recibidas: int

    def snapshot(self) -> dict[str, Any]:
        return {
            "iva_generado": str(self.iva_generado),
            "iva_descontable": str(self.iva_descontable),
            "rete_iva_favor": str(self.rete_iva_favor),
            "saldo": str(self.saldo),
            "saldo_a_favor": str(-self.saldo) if self.saldo < 0 else "0.00",
            "invoices_emitidas": self.invoices_emitidas,
            "invoices_recibidas": self.invoices_recibidas,
        }


def compute_iva(invoices: Iterable[dict[str, Any]]) -> IvaResult:
    """`invoices` ya filtradas por (client_id, período, moneda COP-equivalente)."""
    gen = ZERO
    desc = ZERO
    rete_favor = ZERO
    n_em = n_re = 0
    for inv in invoices:
        direction = inv.get("direction")
        if direction == "emitida":
            n_em += 1
            gen += D(inv.get("iva"))
            rete_favor += D(inv.get("rete_iva"))
        elif direction == "recibida":
            n_re += 1
            if inv.get("is_deductible") is True:
                desc += D(inv.get("iva"))
    saldo = gen - desc - rete_favor
    amount = saldo if saldo > 0 else ZERO
    return IvaResult(
        iva_generado=gen,
        iva_descontable=desc,
        rete_iva_favor=rete_favor,
        saldo=saldo,
        amount=amount,
        invoices_emitidas=n_em,
        invoices_recibidas=n_re,
    )
