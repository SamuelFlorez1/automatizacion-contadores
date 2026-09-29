"""POST /ingest/email — correo entrante (reenviado por n8n) con adjuntos, autenticado por secreto.

n8n (IMAP/Gmail trigger) envía multipart: `sender`, `message_id` y uno o más `attachments`.
Header `x-ingest-secret` debe coincidir con INGEST_EMAIL_SECRET. Cliente se identifica por email remitente.
"""

from __future__ import annotations

import hmac
import re

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import get_settings
from app.db.client import get_service_client
from app.ingest.service import IngestRejected, find_client, ingest_document

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/email")
def ingest_email(
    sender: str = Form(...),
    message_id: str = Form(...),
    attachments: list[UploadFile] = File(...),
    x_ingest_secret: str | None = Header(None),
) -> dict:
    secret = get_settings().ingest_email_secret
    if not secret or not x_ingest_secret or not hmac.compare_digest(secret, x_ingest_secret):
        raise HTTPException(401, "Secreto inválido")

    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", sender)
    db = get_service_client()
    client = find_client(db, email=m.group(0)) if m else None
    if not client:
        return {"status": "ignored", "reason": "remitente no registrado", "results": []}

    results = []
    for i, att in enumerate(attachments):
        try:
            res = ingest_document(
                client=client, source="email", content=att.file.read(), filename=att.filename,
                declared_mime=att.content_type, channel_ref=f"{message_id}#{i}", db=db,
            )
            results.append({"filename": att.filename, **res.__dict__})
        except IngestRejected as e:
            results.append({"filename": att.filename, "outcome": e.outcome, "detail": e.detail})
    return {"status": "ok", "results": results}
