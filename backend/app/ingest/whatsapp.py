"""Webhook de Evolution API (WhatsApp): firma HMAC + idempotencia por messageId y contenido.

Evolution envía `POST /webhooks/evolution` con evento `messages.upsert`. Configurar el webhook
con `webhook_base64: true` para que el media venga en el payload; si no, se descarga vía API.
La firma va en el header `x-signature` (hex HMAC-SHA256 del body crudo con EVOLUTION_WEBHOOK_SECRET).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.db.client import get_service_client
from app.ingest.service import IngestRejected, find_client, ingest_document

log = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

MEDIA_TYPES = {
    "documentMessage": "application/octet-stream",
    "imageMessage": "image/jpeg",
}


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not secret or not signature:
        return False
    sig = signature.removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.lower())


def _fetch_media_b64(message: dict) -> str | None:
    s = get_settings()
    if not (s.evolution_api_url and s.evolution_api_key and s.evolution_instance_name):
        return None
    r = httpx.post(
        f"{s.evolution_api_url.rstrip('/')}/chat/getBase64FromMediaMessage/{s.evolution_instance_name}",
        headers={"apikey": s.evolution_api_key},
        json={"message": message},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("base64")


@router.post("/evolution")
async def evolution_webhook(request: Request) -> dict:
    """Async solo para leer body/firma antes de decodificar; el trabajo bloqueante
    (Supabase, httpx a Evolution) se delega a un helper sync que FastAPI empuja
    al threadpool con `run_in_threadpool` para no ahogar el event loop."""
    from starlette.concurrency import run_in_threadpool

    s = get_settings()
    body = await request.body()
    if not verify_signature(body, request.headers.get("x-signature"), s.evolution_webhook_secret):
        raise HTTPException(401, "Firma inválida")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Body no es JSON válido: {e}") from e

    if str(payload.get("event", "")).lower().replace("_", ".") != "messages.upsert":
        return {"status": "ignored", "reason": "evento no relevante"}
    data = payload.get("data") or {}
    key = data.get("key") or {}
    if key.get("fromMe"):
        return {"status": "ignored", "reason": "mensaje propio"}

    msg = data.get("message") or {}
    kind = next((k for k in MEDIA_TYPES if k in msg), None)
    if not kind:
        return {"status": "ignored", "reason": "sin adjunto"}  # texto: lo atiende el agente (Fase 5)

    return await run_in_threadpool(_handle_media, data, key, msg, kind)


def _handle_media(data: dict, key: dict, msg: dict, kind: str) -> dict:
    db = get_service_client()
    jid = key.get("remoteJid", "")
    phone = jid.split("@")[0]
    client = find_client(db, phone=phone)
    if not client:
        log.warning("whatsapp_unknown_sender", jid=jid)
        return {"status": "ignored", "reason": "remitente no registrado"}

    media = msg[kind]
    b64 = data.get("base64") or media.get("base64")
    if not b64:
        try:
            b64 = _fetch_media_b64({"key": key, "message": msg})
        except Exception as e:
            log.error("whatsapp_media_download_failed", error=str(e))
            raise HTTPException(502, "No se pudo descargar el adjunto") from e
    if not b64:
        raise HTTPException(422, "El webhook no incluye el adjunto (activar webhook_base64)")
    try:
        content = base64.b64decode(b64.split(",")[-1], validate=False)
    except Exception as e:
        raise HTTPException(422, "Adjunto base64 inválido") from e

    try:
        res = ingest_document(
            client=client, source="whatsapp", content=content,
            filename=media.get("fileName") or f"{key.get('id', 'whatsapp')}",
            declared_mime=media.get("mimetype"), channel_ref=key.get("id"), db=db,
        )
    except IngestRejected as e:
        return {"status": e.outcome, "detail": e.detail}
    return {"status": res.outcome, "document_id": res.document_id, "invoice_id": res.invoice_id, "detail": res.detail}
