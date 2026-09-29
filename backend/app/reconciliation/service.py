"""Persistencia y orquestación de conciliación contra Supabase.

Este módulo pega el motor puro (`engine.py`) con la base de datos:
- normaliza el CSV → `bank_transactions` (idempotente por `(firm_id, dedupe_key)`)
- crea/recupera `bank_accounts` a partir del hint del CSV
- corre `reconcile()` con las facturas pendientes del cliente
- inserta `reconciliation_matches` y actualiza `bank_transactions.match_status`
- actualiza `invoices.payment_status` cuando el match es exacto
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from app.reconciliation.csv_parser import BankAccountHint, ParsedStatement, parse_bank_csv
from app.reconciliation.engine import MatchResult, ReconcileSummary, reconcile

log = structlog.get_logger()


@dataclass
class BankUploadResult:
    bank_account_id: str
    inserted: int
    duplicates: int
    summary: ReconcileSummary


# ------------------------------------------------------------ bank account
def get_or_create_bank_account(db: Client, *, firm_id: str, client_id: str, hint: BankAccountHint) -> str:
    q = (
        db.table("bank_accounts").select("id")
        .eq("firm_id", firm_id).eq("client_id", client_id)
        .eq("bank_name", hint.bank_name).eq("account_number_masked", hint.account_number_masked)
        .execute().data
    )
    if q:
        return q[0]["id"]
    row = (
        db.table("bank_accounts").insert(
            {
                "firm_id": firm_id, "client_id": client_id,
                "bank_name": hint.bank_name or "Banco",
                "account_type": hint.account_type or "corriente",
                "account_number_masked": hint.account_number_masked or "****",
                "currency": hint.currency or "COP",
            }
        ).execute().data[0]
    )
    return row["id"]


# ------------------------------------------------------------ txn upsert
def _insert_transactions(
    db: Client, *, firm_id: str, client_id: str, bank_account_id: str, parsed: ParsedStatement
) -> tuple[list[dict], int]:
    """Inserta transacciones ignorando duplicados. Devuelve (nuevas, duplicadas)."""
    inserted: list[dict] = []
    duplicates = 0
    for tx in parsed.txns:
        payload = {
            "firm_id": firm_id, "client_id": client_id, "bank_account_id": bank_account_id,
            "tx_date": tx.tx_date.isoformat(), "description": tx.description,
            "reference": tx.reference, "amount": str(tx.amount), "currency": tx.currency,
            "balance_after": str(tx.balance_after) if tx.balance_after is not None else None,
            "dedupe_key": tx.dedupe_key,
        }
        try:
            row = db.table("bank_transactions").insert(payload).execute().data[0]
            inserted.append(row)
        except APIError as e:
            if e.code == "23505":  # dedupe
                duplicates += 1
                continue
            raise
    return inserted, duplicates


# ------------------------------------------------------------ persist matches
def _persist_matches(
    db: Client, *, firm_id: str, client_id: str, matches: list[MatchResult], status: dict[str, str]
) -> None:
    if matches:
        rows = [
            {**m.as_row(), "firm_id": firm_id, "client_id": client_id}
            for m in matches
        ]
        db.table("reconciliation_matches").insert(rows).execute()

    # Actualizar match_status por transacción.
    per_status: dict[str, list[str]] = {}
    for tx_id, st in status.items():
        per_status.setdefault(st, []).append(tx_id)
    for st, ids in per_status.items():
        db.table("bank_transactions").update({"match_status": st}).in_("id", ids).execute()

    # Facturas totalmente pagadas por match exacto → payment_status='paid'.
    exact_invoice_ids = [m.invoice_id for m in matches if m.match_type == "exact" and m.invoice_id]
    if exact_invoice_ids:
        db.table("invoices").update({"payment_status": "paid"}).in_("id", exact_invoice_ids).execute()


# ------------------------------------------------------------ orquestación
def _load_client_invoices(db: Client, client_id: str) -> list[dict]:
    return (
        db.table("invoices")
        .select("id, invoice_number, cufe, direction, supplier_name, supplier_nit, "
                "issue_date, total, total_cop, currency, payment_status")
        .eq("client_id", client_id).neq("payment_status", "paid").execute().data
    )


def _load_client_transactions(db: Client, client_id: str, *, only_unmatched: bool = True) -> list[dict]:
    q = (
        db.table("bank_transactions")
        .select("id, bank_account_id, tx_date, description, reference, amount, currency, match_status")
        .eq("client_id", client_id)
    )
    if only_unmatched:
        q = q.in_("match_status", ["unmatched"])
    return q.execute().data


def reconcile_client(db: Client, *, firm_id: str, client_id: str) -> ReconcileSummary:
    txns = _load_client_transactions(db, client_id, only_unmatched=True)
    invoices = _load_client_invoices(db, client_id)
    # bank_transactions.tx_date llega como str "YYYY-MM-DD" de supabase.
    for t in txns:
        if isinstance(t["tx_date"], str):
            t["tx_date"] = date.fromisoformat(t["tx_date"])
    matches, status, summary = reconcile(txns, invoices)
    _persist_matches(db, firm_id=firm_id, client_id=client_id, matches=matches, status=status)
    return summary


def ingest_bank_csv(
    db: Client, *, firm_id: str, client_id: str, content: bytes, filename: str | None = None,
) -> BankUploadResult:
    parsed = parse_bank_csv(content)
    account_id = get_or_create_bank_account(db, firm_id=firm_id, client_id=client_id, hint=parsed.account)
    inserted, duplicates = _insert_transactions(
        db, firm_id=firm_id, client_id=client_id, bank_account_id=account_id, parsed=parsed
    )
    log.info("bank_csv_ingested", client_id=client_id, inserted=len(inserted), duplicates=duplicates,
             filename=filename)
    # Correr conciliación sobre TODO lo pendiente del cliente (no solo lo nuevo)
    # para poder emparejar con facturas que llegaron después.
    summary = reconcile_client(db, firm_id=firm_id, client_id=client_id)
    return BankUploadResult(
        bank_account_id=account_id, inserted=len(inserted), duplicates=duplicates, summary=summary,
    )
