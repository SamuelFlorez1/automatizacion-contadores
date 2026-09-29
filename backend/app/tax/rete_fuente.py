"""Retención en la fuente mensual (Formulario 350).

El agente de retención (nuestro cliente cuando `is_agente_retencion=True`) suma
lo que retuvo a proveedores durante el mes y lo declara/paga a la DIAN.

Simplificación demo:
- Se toma directamente el valor `rete_fuente` de cada factura `recibida` del mes.
- Se agrupa por cuenta PUC para exponer el detalle por concepto en el snapshot.
- No se aplican tarifas nuevas: la retención se calculó al momento de la factura.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.tax._money import D, ZERO


# Concepto tributario a partir de la cuenta PUC (raíz de 4 dígitos).
# Códigos DIAN son los usados en el Formulario 350 (columnas del anexo).
PUC_ROOT_TO_CONCEPTO = {
    "5110": "honorarios",
    "5115": "servicios_tecnicos",
    "5120": "servicios",
    "5135": "servicios",
    "5140": "arrendamientos",
    "5145": "servicios",
    "5155": "servicios",
    "5160": "publicidad",
    "5195": "otros",
    "6135": "compras",
    "6205": "compras",
}


def concepto_from_puc(puc: str | None) -> str:
    if not puc:
        return "otros"
    return PUC_ROOT_TO_CONCEPTO.get(puc[:4], "otros")


@dataclass
class ReteFuenteResult:
    amount: Decimal
    by_concepto: dict[str, Decimal]
    invoice_count: int

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": str(self.amount),
            "by_concepto": {k: str(v) for k, v in self.by_concepto.items()},
            "invoice_count": self.invoice_count,
        }


def compute_rete_fuente(invoices: Iterable[dict[str, Any]]) -> ReteFuenteResult:
    """`invoices` deben ser recibidas del mes y del cliente agente de retención."""
    by_concepto: dict[str, Decimal] = defaultdict(lambda: ZERO)
    total = ZERO
    n = 0
    for inv in invoices:
        if inv.get("direction") != "recibida":
            continue
        val = D(inv.get("rete_fuente"))
        if val <= 0:
            continue
        total += val
        by_concepto[concepto_from_puc(inv.get("puc_account"))] += val
        n += 1
    return ReteFuenteResult(amount=total, by_concepto=dict(by_concepto), invoice_count=n)
