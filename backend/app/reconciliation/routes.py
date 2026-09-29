"""Endpoints de conciliación bancaria y clasificación PUC.

- POST /bank/upload            → subir extracto CSV (staff).
- POST /bank/reconcile/{cid}   → re-correr matching sobre lo pendiente del cliente.
- POST /invoices/{id}/classify → clasificar una factura en PUC.
- POST /clients/{cid}/classify → clasificar en batch todas las facturas del cliente sin cuenta.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import CurrentUser, get_current_user
from app.classification.puc import classify_and_persist
from app.db.client import get_service_client
from app.reconciliation.csv_parser import CsvParseError
from app.reconciliation.service import ingest_bank_csv, reconcile_client

router = APIRouter(tags=["reconciliation"])


def _require_client(db, user: CurrentUser, client_id: str) -> dict:
    """Verifica que `client_id` pertenece al despacho del usuario y (si cliente) al propio."""
    if user.role == "client" and user.client_id != client_id:
        raise HTTPException(403, "Solo puedes operar sobre tu propia cuenta")
    rows = db.table("clients").select("id, firm_id").eq("id", client_id).eq("firm_id", user.firm_id).execute().data
    if not rows:
        raise HTTPException(404, "Cliente no encontrado")
    return rows[0]


@router.post("/bank/upload")
def upload_bank_statement(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not user.is_staff:
        raise HTTPException(403, "Solo el equipo del despacho puede subir extractos")
    db = get_service_client()
    _require_client(db, user, client_id)
    content = file.file.read()
    if not content:
        raise HTTPException(422, "Archivo vacío")
    try:
        res = ingest_bank_csv(
            db, firm_id=user.firm_id, client_id=client_id, content=content, filename=file.filename,
        )
    except CsvParseError as e:
        raise HTTPException(422, f"CSV inválido: {e}") from e
    return {
        "bank_account_id": res.bank_account_id,
        "inserted": res.inserted,
        "duplicates": res.duplicates,
        **res.summary.as_dict(),
    }


@router.post("/bank/reconcile/{client_id}")
def reconcile_endpoint(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not user.is_staff:
        raise HTTPException(403, "Solo staff")
    db = get_service_client()
    _require_client(db, user, client_id)
    summary = reconcile_client(db, firm_id=user.firm_id, client_id=client_id)
    return summary.as_dict()


@router.post("/invoices/{invoice_id}/classify")
def classify_one(
    invoice_id: str,
    user: CurrentUser = Depends(get_current_user),
    force_rules: bool = False,
) -> dict:
    if not user.is_staff:
        raise HTTPException(403, "Solo staff")
    db = get_service_client()
    # Verificar que la factura pertenece al despacho.
    rows = db.table("invoices").select("id, firm_id").eq("id", invoice_id).execute().data
    if not rows or rows[0]["firm_id"] != user.firm_id:
        raise HTTPException(404, "Factura no encontrada")
    try:
        cls = classify_and_persist(db, invoice_id, force_rules=force_rules)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {
        "invoice_id": invoice_id,
        "puc_account": cls.puc_account,
        "confidence": cls.confidence,
        "rationale": cls.rationale,
        "source": cls.source,
    }


@router.post("/clients/{client_id}/classify")
def classify_client_batch(
    client_id: str,
    user: CurrentUser = Depends(get_current_user),
    force_rules: bool = False,
    limit: int = 100,
) -> dict:
    if not user.is_staff:
        raise HTTPException(403, "Solo staff")
    db = get_service_client()
    _require_client(db, user, client_id)
    rows = (
        db.table("invoices").select("id")
        .eq("client_id", client_id).is_("puc_account", "null")
        .limit(limit).execute().data
    )
    done = 0
    errors: list[str] = []
    for r in rows:
        try:
            classify_and_persist(db, r["id"], force_rules=force_rules)
            done += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{r['id']}: {e}")
    return {"classified": done, "pending": len(rows) - done, "errors": errors}
