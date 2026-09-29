"""POST /ingest/upload — subida manual desde el dashboard (staff o cliente autenticado)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import CurrentUser, get_current_user
from app.db.client import get_service_client
from app.ingest.service import IngestRejected, ingest_document

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    client_id: str | None = Form(None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    db = get_service_client()
    # Un cliente solo sube a su propia cuenta; el staff elige cliente de su despacho.
    target_id = user.client_id if user.role == "client" else client_id
    if not target_id:
        raise HTTPException(422, "client_id es obligatorio")
    rows = db.table("clients").select("id, firm_id, nit").eq("id", target_id).eq("firm_id", user.firm_id).execute().data
    if not rows:
        raise HTTPException(404, "Cliente no encontrado")
    content = file.file.read()
    try:
        res = ingest_document(
            client=rows[0], source="upload", content=content,
            filename=file.filename, declared_mime=file.content_type, db=db,
        )
    except IngestRejected as e:
        raise HTTPException(429 if e.outcome == "rate_limited" else 422, e.detail) from e
    return res.__dict__
