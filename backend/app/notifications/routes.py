"""Endpoints internos disparados por n8n (cron) para enviar recordatorios."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.auth import CurrentUser, get_current_user
from app.config import get_settings
from app.notifications.reminders import run_reminders

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _cron_auth(request: Request) -> None:
    """Autenticación simple por header `x-cron-secret` para n8n.
    Reutiliza `ingest_email_secret` como shared secret si está seteado."""
    secret = get_settings().ingest_email_secret
    if not secret:
        raise HTTPException(500, "Secret de cron no configurado (ingest_email_secret)")
    if request.headers.get("x-cron-secret") != secret:
        raise HTTPException(401, "x-cron-secret inválido")


@router.post("/reminders/run")
async def run_reminders_endpoint(request: Request, today: str | None = None) -> dict:
    """Cron n8n → dispara recordatorios de vencimiento (5/2/0 días).
    `today` opcional en formato YYYY-MM-DD para debugging."""
    _cron_auth(request)
    d = date.fromisoformat(today) if today else None
    return await run_in_threadpool(run_reminders, None, today=d)


@router.post("/reminders/preview")
async def preview_reminders(
    today: str | None = None,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Vista previa autenticada por JWT (para staff)."""
    if not user.is_staff:
        raise HTTPException(403, "Solo staff")
    d = date.fromisoformat(today) if today else None
    return await run_in_threadpool(run_reminders, user.firm_id, today=d)
