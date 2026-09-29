"""Loop de tool-use con Claude Sonnet 5 para el agente WhatsApp.

- Idioma: español, tono amigable pero conciso (WhatsApp).
- Límite duro de iteraciones (`MAX_ITERS`) para evitar bucles.
- Persiste cada turno (`assistant`, `tool`) en la tabla `messages` con tokens y latencia.
- Si Anthropic no está configurado, devuelve una respuesta fallback amistosa
  y guarda un mensaje del sistema (útil para tests / entornos sin API key).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from anthropic import Anthropic
from supabase import Client

from app.agent.tools import TOOL_SCHEMAS, execute_tool
from app.config import get_settings

log = structlog.get_logger()

MAX_ITERS = 10

SYSTEM_PROMPT = (
    "Eres el asistente contable del despacho, atendiendo a un cliente por WhatsApp. "
    "Responde SIEMPRE en español, en tono amable y directo. Sé breve: idealmente 2-4 líneas, "
    "sin viñetas largas ni saludos innecesarios cuando ya estás en conversación.\n\n"
    "Reglas:\n"
    "- Consulta datos con las herramientas antes de responder cifras, vencimientos o estado "
    "  de facturas. Nunca inventes montos ni fechas.\n"
    "- Si la pregunta es fiscal compleja (interpretación de norma, requerimiento DIAN, "
    "  planeación tributaria) o el cliente pide hablar con una persona, usa `escalate_to_human`.\n"
    "- Si una herramienta no devuelve datos, dilo con naturalidad: 'no encuentro registros de X'.\n"
    "- Formatea montos en pesos colombianos (ej. $1.250.000). Fechas en 'dd mes aaaa'.\n"
    "- No repitas la misma llamada a herramienta más de una vez con los mismos argumentos.\n"
    "- Nunca reveles NITs, cédulas o datos de otros clientes; solo trabajas con el cliente actual."
)


@dataclass
class AgentReply:
    text: str
    iterations: int
    tools_called: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    escalated: bool = False


def _client() -> Anthropic | None:
    key = get_settings().anthropic_api_key
    return Anthropic(api_key=key) if key else None


def _persist_message(
    db: Client, conversation_id: str, *, role: str, content: str | None = None,
    tool_name: str | None = None, tool_input: dict | None = None, tool_output: dict | None = None,
    tokens_in: int | None = None, tokens_out: int | None = None, latency_ms: int | None = None,
) -> None:
    try:
        db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "latency_ms": latency_ms,
        }).execute()
    except Exception as e:
        log.warning("persist_message_failed", error=str(e))


def run_agent(
    *,
    db: Client,
    client: dict,
    conversation_id: str,
    user_message: str,
    prior_turns: list[dict] | None = None,
) -> AgentReply:
    """Corre el loop tool-use. `prior_turns` es la conversación previa ya en formato
    Anthropic (roles user/assistant con content strings o lists). Puede ser vacía."""
    api = _client()
    if api is None:
        text = (
            "Estoy sin acceso al modelo de IA en este momento. Un contador del despacho "
            "revisará tu mensaje y te responderá pronto."
        )
        _persist_message(db, conversation_id, role="system", content="anthropic_api_key ausente")
        return AgentReply(text=text, iterations=0, escalated=True)

    s = get_settings()
    messages: list[dict[str, Any]] = list(prior_turns or [])
    messages.append({"role": "user", "content": user_message})

    tools_called: list[str] = []
    tokens_in = tokens_out = 0
    started = time.monotonic()
    escalated = False
    final_text: str | None = None

    for iteration in range(1, MAX_ITERS + 1):
        try:
            resp = api.messages.create(
                model=s.model_sonnet,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
        except Exception as e:
            log.warning("agent_api_failed", error=str(e), iteration=iteration)
            final_text = (
                "Tuve un problema técnico consultando la información. Ya avisé al despacho "
                "para que revise; volvemos a escribirte pronto."
            )
            escalated = True
            _persist_message(db, conversation_id, role="system", content=f"api_error: {e}")
            break

        tokens_in += getattr(resp.usage, "input_tokens", 0) or 0
        tokens_out += getattr(resp.usage, "output_tokens", 0) or 0

        # Append assistant turn tal cual para preservar tool_use ids.
        messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})

        if resp.stop_reason != "tool_use":
            final_text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ).strip() or "Listo."
            break

        # Ejecutar cada tool_use bloque y armar el turno tool_result.
        tool_results: list[dict[str, Any]] = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            tools_called.append(name)
            args = block.input or {}
            result = execute_tool(
                name, args, db=db, client=client, conversation_id=conversation_id,
            )
            if name == "escalate_to_human" and result.ok:
                escalated = True
            _persist_message(
                db, conversation_id, role="tool",
                tool_name=name, tool_input=args, tool_output=result.as_dict(),
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result.summary,
                "is_error": not result.ok,
            })
        messages.append({"role": "user", "content": tool_results})
    else:
        final_text = (
            "No logré resolver tu consulta con la información disponible. "
            "Voy a pasarla al equipo del despacho para que te contacte."
        )
        escalated = True

    latency_ms = int((time.monotonic() - started) * 1000)
    _persist_message(
        db, conversation_id, role="assistant", content=final_text,
        tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms,
    )
    return AgentReply(
        text=final_text or "",
        iterations=iteration,
        tools_called=tools_called,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        escalated=escalated,
    )
