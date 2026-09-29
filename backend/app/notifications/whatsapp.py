"""Envío de mensajes de WhatsApp vía Evolution API.

Uso mínimo: `send_text(phone, text)`. `phone` puede venir con o sin '+' y con o sin
código de país; se normaliza a dígitos y se antepone '57' si tiene 10 dígitos.

Si no hay credenciales configuradas, la función registra un log y devuelve
`{'ok': False, 'reason': 'evolution_not_configured'}` — útil para tests y para
correr la demo sin Evolution.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = "57" + digits  # Colombia por defecto
    return digits


def send_text(phone: str, text: str, *, timeout: float = 15.0) -> dict[str, Any]:
    s = get_settings()
    if not (s.evolution_api_url and s.evolution_api_key and s.evolution_instance_name):
        log.info("evolution_not_configured", to=phone, preview=text[:80])
        return {"ok": False, "reason": "evolution_not_configured", "to": phone}

    to = normalize_phone(phone)
    url = f"{s.evolution_api_url.rstrip('/')}/message/sendText/{s.evolution_instance_name}"
    payload = {"number": to, "text": text, "options": {"delay": 0, "presence": "composing"}}
    try:
        r = httpx.post(url, headers={"apikey": s.evolution_api_key}, json=payload, timeout=timeout)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.error("evolution_send_failed", error=str(e), to=to)
        return {"ok": False, "reason": "http_error", "detail": str(e), "to": to}
    return {"ok": True, "to": to, "response": r.json() if r.content else {}}
