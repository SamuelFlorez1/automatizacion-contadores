"""Endpoint del agente conversacional.

`POST /agent/message` es el único endpoint público:
- identifica al cliente por `phone` (últimos 10 dígitos) o `client_id`,
- reabre o crea la conversación (por `channel + external_id`),
- corre el loop de tool-use y devuelve la respuesta lista para enviar.

n8n lo llama después de recibir un mensaje de texto por Evolution.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.agent.loop import run_agent
from app.db.client import get_service_client
from app.ingest.service import find_client

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentMessageIn(BaseModel):
    phone: str | None = Field(default=None, description="Teléfono E.164 o local, se normaliza a 10 dígitos.")
    client_id: str | None = None
    channel: Literal["whatsapp", "web", "email"] = "whatsapp"
    external_id: str | None = Field(default=None, description="ID de conversación en la plataforma (chat/thread).")
    message: str = Field(min_length=1, max_length=4000)


class AgentMessageOut(BaseModel):
    text: str
    conversation_id: str
    escalated: bool
    tools_called: list[str]
    iterations: int
    tokens_in: int
    tokens_out: int
    latency_ms: int


def _get_or_create_conversation(db, *, firm_id: str, client_id: str, channel: str,
                                external_id: str | None, phone: str | None) -> dict:
    if external_id:
        rows = (db.table("conversations").select("*")
                .eq("channel", channel).eq("external_id", external_id)
                .execute().data)
        if rows:
            return rows[0]
    # Sin external_id: reusa la última conversación activa por cliente+canal.
    if not external_id:
        rows = (db.table("conversations").select("*")
                .eq("client_id", client_id).eq("channel", channel).eq("status", "active")
                .order("started_at", desc=True).limit(1).execute().data)
        if rows:
            return rows[0]
    return db.table("conversations").insert({
        "firm_id": firm_id, "client_id": client_id, "channel": channel,
        "external_id": external_id, "phone": phone,
    }).execute().data[0]


def _prior_turns(db, conversation_id: str, limit: int = 8) -> list[dict]:
    """Últimos N intercambios usuario/asistente en formato Anthropic (solo texto)."""
    rows = (db.table("messages")
            .select("role, content, created_at")
            .eq("conversation_id", conversation_id)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=True).limit(limit)
            .execute().data)
    rows = list(reversed(rows))
    out: list[dict] = []
    for r in rows:
        if not r.get("content"):
            continue
        out.append({"role": r["role"], "content": r["content"]})
    return out


def _run(payload: AgentMessageIn) -> AgentMessageOut:
    db = get_service_client()

    client = None
    if payload.client_id:
        rows = db.table("clients").select("id, firm_id, nit, phone").eq("id", payload.client_id).execute().data
        client = rows[0] if rows else None
    elif payload.phone:
        client = find_client(db, phone=payload.phone)

    if client is None:
        raise HTTPException(404, "Cliente no encontrado por teléfono/ID")

    conv = _get_or_create_conversation(
        db, firm_id=client["firm_id"], client_id=client["id"],
        channel=payload.channel, external_id=payload.external_id, phone=payload.phone,
    )

    # Persistir el mensaje del usuario ANTES de calcular prior_turns para que
    # el próximo turno lo vea, pero no lo incluimos en `prior_turns` porque
    # ya lo pasamos como user_message al loop.
    db.table("messages").insert({
        "conversation_id": conv["id"], "role": "user", "content": payload.message,
    }).execute()
    db.table("conversations").update({"last_message_at": "now()"}).eq("id", conv["id"]).execute()

    prior = _prior_turns(db, conv["id"])
    # Quitar el último 'user' que acabamos de insertar para no duplicar.
    if prior and prior[-1]["role"] == "user" and prior[-1]["content"] == payload.message:
        prior = prior[:-1]

    reply = run_agent(
        db=db, client=client, conversation_id=conv["id"],
        user_message=payload.message, prior_turns=prior,
    )
    return AgentMessageOut(
        text=reply.text, conversation_id=conv["id"], escalated=reply.escalated,
        tools_called=reply.tools_called, iterations=reply.iterations,
        tokens_in=reply.tokens_in, tokens_out=reply.tokens_out, latency_ms=reply.latency_ms,
    )


@router.post("/message", response_model=AgentMessageOut)
async def agent_message(payload: AgentMessageIn) -> AgentMessageOut:
    return await run_in_threadpool(_run, payload)
