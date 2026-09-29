"""Motor de conciliación bancaria.

Estrategias, por orden de prioridad:

1. `exact`      — la referencia bancaria contiene el `invoice_number` (o CUFE)
                  Y el monto absoluto casa con el total de la factura (±$1 COP tolerancia).
2. `exact`      — monto y fecha ±3 días con una única factura candidata del proveedor
                  identificado por nombre en la descripción.
3. `fuzzy`      — monto ±2 % y nombre del proveedor con similitud ≥ 0.7 en la descripción
                  dentro de una ventana de ±10 días. Confianza < 1.
4. `transfer_internal` — dos transacciones del mismo cliente, mismo día, montos opuestos
                         (±1 COP) y descripciones que huelen a "TRASLADO"/"TRANSFERENCIA
                         INTERNA". No crea factura, solo marca ambas transacciones.

Salida: lista de `MatchResult` con los datos que van a `reconciliation_matches`.
Los `bank_transactions.match_status` se actualizan por el caller.

Diseñado para trabajar con dicts planos (los que devuelve Supabase) de modo que sea
trivial de testear sin la DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Iterable

import pandas as pd

MatchType = str  # 'exact' | 'fuzzy' | 'manual' | 'transfer_internal'


@dataclass
class MatchResult:
    bank_transaction_id: str
    invoice_id: str | None
    match_type: MatchType
    confidence: float
    matched_amount: Decimal
    reason: str

    def as_row(self) -> dict[str, Any]:
        return {
            "bank_transaction_id": self.bank_transaction_id,
            "invoice_id": self.invoice_id,
            "match_type": self.match_type,
            "confidence": round(float(self.confidence), 3),
            "matched_amount": str(self.matched_amount),
            "reason": self.reason[:500],
        }


# ---------------------------------------------------------- helpers
_TRANSFER_RE = re.compile(
    r"\b(traslado|transferencia\s+(interna|entre\s+cuentas)|movimiento\s+interno)\b",
    re.I,
)
_ATM_RE = re.compile(r"\b(retiro\s+atm|cajero|atm)\b", re.I)


def _dec(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v)) if v is not None else Decimal("0")


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _amount_close(a: Decimal, b: Decimal, *, abs_tol: str = "1", rel_tol: float | None = None) -> bool:
    diff = abs(a - b)
    if diff <= Decimal(abs_tol):
        return True
    if rel_tol is not None and b != 0 and diff / abs(b) <= Decimal(str(rel_tol)):
        return True
    return False


# ---------------------------------------------------------- estrategias
def _try_exact_by_reference(tx: dict, invoices: list[dict]) -> MatchResult | None:
    """Match por referencia bancaria = número de factura.

    Es aceptable que el monto no cuadre al peso: en Colombia el pago suele descontar
    retenciones (rete-fuente/IVA/ICA) del total facturado. Aceptamos hasta 25 % de
    diferencia (cubre combinaciones típicas de retenciones) y ajustamos la confianza.
    """
    ref = (tx.get("reference") or "").strip()
    amount = abs(_dec(tx["amount"]))
    if not ref:
        return None
    for inv in invoices:
        inv_num = (inv.get("invoice_number") or "").strip()
        cufe = (inv.get("cufe") or "").strip()
        if not inv_num:
            continue
        hit = inv_num.lower() in ref.lower() or (cufe and len(cufe) >= 20 and cufe[:20] in ref)
        if not hit:
            continue
        inv_total = _dec(inv.get("total_cop") or inv.get("total"))
        if inv_total == 0:
            continue
        rel = abs(amount - inv_total) / inv_total
        if rel > Decimal("0.25"):
            # Referencia coincide pero monto es demasiado distinto: sospechoso, dejar para revisión humana.
            return MatchResult(
                bank_transaction_id=tx["id"], invoice_id=inv["id"], match_type="fuzzy",
                confidence=0.55, matched_amount=amount,
                reason=f"Referencia {inv_num} pero monto difiere {rel:.0%}",
            )
        # Amount cuadra (exacto o con retenciones): match exacto.
        note = "referencia" if _amount_close(amount, inv_total, abs_tol="1") else f"referencia (dif. {rel:.1%} por retenciones)"
        return MatchResult(
            bank_transaction_id=tx["id"], invoice_id=inv["id"], match_type="exact",
            confidence=1.0 if rel < Decimal("0.02") else 0.92,
            matched_amount=amount, reason=f"Match por {note}: factura {inv_num}",
        )
    return None


def _try_exact_by_amount_supplier(tx: dict, invoices: list[dict]) -> MatchResult | None:
    amount = abs(_dec(tx["amount"]))
    tx_date: date = tx["tx_date"] if isinstance(tx["tx_date"], date) else date.fromisoformat(str(tx["tx_date"]))
    desc = tx.get("description") or ""

    candidates: list[tuple[dict, float]] = []
    for inv in invoices:
        supplier = inv.get("supplier_name") or ""
        if not supplier:
            continue
        inv_total = _dec(inv.get("total_cop") or inv.get("total"))
        if not _amount_close(amount, inv_total, abs_tol="1"):
            continue
        inv_date = inv["issue_date"] if isinstance(inv["issue_date"], date) else date.fromisoformat(str(inv["issue_date"]))
        if abs((tx_date - inv_date).days) > 45:
            continue
        # Coincidencia razonable si el nombre del proveedor está contenido en la descripción.
        sim = _similar(supplier, desc)
        if sim >= 0.55 or _norm(supplier)[:8] and _norm(supplier)[:8] in _norm(desc):
            candidates.append((inv, sim))

    if not candidates:
        return None
    if len(candidates) == 1:
        inv, sim = candidates[0]
        return MatchResult(
            bank_transaction_id=tx["id"], invoice_id=inv["id"], match_type="exact",
            confidence=min(0.98, 0.85 + sim / 10), matched_amount=amount,
            reason=f"Monto+proveedor únicos ({inv.get('supplier_name')}, factura {inv.get('invoice_number')})",
        )
    # Múltiples candidatos: prioriza mayor similitud de nombre; a igual similitud, fecha más cercana.
    def _rank(c):
        inv, sim = c
        inv_date = inv["issue_date"] if isinstance(inv["issue_date"], date) else date.fromisoformat(str(inv["issue_date"]))
        return (-round(sim, 2), abs((tx_date - inv_date).days))
    candidates.sort(key=_rank)
    inv, sim = candidates[0]
    return MatchResult(
        bank_transaction_id=tx["id"], invoice_id=inv["id"], match_type="fuzzy",
        confidence=0.7, matched_amount=amount,
        reason=f"Monto+proveedor con {len(candidates)} candidatos; escogida factura {inv.get('invoice_number')} por proximidad",
    )


def _try_fuzzy(tx: dict, invoices: list[dict]) -> MatchResult | None:
    amount = abs(_dec(tx["amount"]))
    tx_date: date = tx["tx_date"] if isinstance(tx["tx_date"], date) else date.fromisoformat(str(tx["tx_date"]))
    desc = tx.get("description") or ""

    best: tuple[dict, float, Decimal] | None = None
    for inv in invoices:
        supplier = inv.get("supplier_name") or ""
        if not supplier:
            continue
        inv_total = _dec(inv.get("total_cop") or inv.get("total"))
        if inv_total == 0:
            continue
        rel = abs(amount - inv_total) / inv_total
        if rel > Decimal("0.02"):
            continue
        inv_date = inv["issue_date"] if isinstance(inv["issue_date"], date) else date.fromisoformat(str(inv["issue_date"]))
        if abs((tx_date - inv_date).days) > 10:
            continue
        sim = _similar(supplier, desc)
        if sim < 0.7:
            continue
        score = sim - float(rel)  # mejor cuanto más cerca en monto y nombre
        if best is None or score > best[1]:
            best = (inv, score, inv_total)

    if best is None:
        return None
    inv, score, inv_total = best
    return MatchResult(
        bank_transaction_id=tx["id"],
        invoice_id=inv["id"],
        match_type="fuzzy",
        confidence=max(0.6, min(0.9, 0.6 + score / 2)),
        matched_amount=amount,
        reason=f"Aproximado por nombre+monto ({inv.get('supplier_name')})",
    )


def _find_internal_transfers(txns: list[dict]) -> list[tuple[MatchResult, MatchResult]]:
    """Empareja debitos y creditos entre cuentas del mismo cliente."""
    out: list[tuple[MatchResult, MatchResult]] = []
    used: set[str] = set()

    # Agrupar por fecha para eficiencia
    by_date: dict[date, list[dict]] = {}
    for tx in txns:
        d = tx["tx_date"] if isinstance(tx["tx_date"], date) else date.fromisoformat(str(tx["tx_date"]))
        by_date.setdefault(d, []).append(tx)

    for day, group in by_date.items():
        for i, tx in enumerate(group):
            if tx["id"] in used:
                continue
            if not _TRANSFER_RE.search(tx.get("description") or ""):
                continue
            for other in group[i + 1 :]:
                if other["id"] in used or other["bank_account_id"] == tx["bank_account_id"]:
                    continue
                if not _TRANSFER_RE.search(other.get("description") or ""):
                    continue
                a1 = _dec(tx["amount"])
                a2 = _dec(other["amount"])
                if not _amount_close(a1, -a2, abs_tol="1"):
                    continue
                m1 = MatchResult(tx["id"], None, "transfer_internal", 1.0, abs(a1),
                                 f"Traslado entre cuentas ({day.isoformat()})")
                m2 = MatchResult(other["id"], None, "transfer_internal", 1.0, abs(a2),
                                 f"Traslado entre cuentas ({day.isoformat()})")
                out.append((m1, m2))
                used.add(tx["id"])
                used.add(other["id"])
                break
    return out


# ---------------------------------------------------------- API principal
@dataclass
class ReconcileSummary:
    total_transactions: int
    exact: int = 0
    fuzzy: int = 0
    transfer: int = 0
    unmatched: int = 0
    review: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "total_transactions": self.total_transactions,
            "exact": self.exact,
            "fuzzy": self.fuzzy,
            "transfer": self.transfer,
            "unmatched": self.unmatched,
            "review": self.review,
        }


def reconcile(
    bank_txns: Iterable[dict],
    invoices: Iterable[dict],
) -> tuple[list[MatchResult], dict[str, str], ReconcileSummary]:
    """Devuelve (matches, status_por_txn, resumen).

    `status_por_txn`: dict `{bank_transaction_id: match_status}` con los estados a
    escribir en `bank_transactions.match_status`.
    """
    txns = list(bank_txns)
    invoices_list = list(invoices)
    # Filtrar solo facturas no pagadas para reducir candidatos.
    pending_invoices = [i for i in invoices_list if i.get("payment_status") != "paid"]

    matches: list[MatchResult] = []
    status: dict[str, str] = {}

    # 1. Traslados internos primero (evita que se emparejen mal con facturas).
    transfers = _find_internal_transfers(txns)
    matched_ids: set[str] = set()
    for m1, m2 in transfers:
        matches.extend([m1, m2])
        matched_ids.add(m1.bank_transaction_id)
        matched_ids.add(m2.bank_transaction_id)
        status[m1.bank_transaction_id] = "matched"
        status[m2.bank_transaction_id] = "matched"

    used_invoices: set[str] = set()

    def _pool() -> list[dict]:
        return [i for i in pending_invoices if i["id"] not in used_invoices]

    # 2. Exact por referencia → 3. exact por monto+proveedor → 4. fuzzy.
    for tx in txns:
        if tx["id"] in matched_ids:
            continue
        # Retiros ATM u operaciones sin referencia posible se dejan como unmatched.
        if _ATM_RE.search(tx.get("description") or "") and not (tx.get("reference") or ""):
            status[tx["id"]] = "unmatched"
            continue

        for strat in (_try_exact_by_reference, _try_exact_by_amount_supplier, _try_fuzzy):
            m = strat(tx, _pool())
            if m is not None:
                matches.append(m)
                matched_ids.add(tx["id"])
                if m.invoice_id:
                    used_invoices.add(m.invoice_id)
                status[tx["id"]] = "matched" if m.match_type == "exact" else "review"
                break
        else:
            status[tx["id"]] = "unmatched"

    summary = ReconcileSummary(total_transactions=len(txns))
    for m in matches:
        if m.match_type == "exact":
            summary.exact += 1
        elif m.match_type == "fuzzy":
            summary.fuzzy += 1
        elif m.match_type == "transfer_internal":
            summary.transfer += 1
    for s in status.values():
        if s == "review":
            summary.review += 1
        elif s == "unmatched":
            summary.unmatched += 1
    # Transacciones sin veredicto explícito → unmatched (por si acaso)
    for tx in txns:
        status.setdefault(tx["id"], "unmatched")

    return matches, status, summary


# ---------------------------------------------------------- ayudante DataFrame
def matches_to_dataframe(matches: list[MatchResult]) -> pd.DataFrame:
    """Vista tabular útil para reportes y depuración."""
    return pd.DataFrame([m.as_row() for m in matches])
