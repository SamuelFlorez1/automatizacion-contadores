# Fase 5 — Agente WhatsApp + n8n

Cerrada 2026-09-28.

## Qué se construyó

Agente conversacional en español que responde por WhatsApp usando datos reales del cliente (facturas, obligaciones fiscales, documentos pendientes), más el cron diario de recordatorios de vencimiento.

### Estructura

- `backend/app/agent/tools.py` — 5 tools con schema Anthropic + ejecutores puros:
  - `get_pending_invoices` — documentos con error + facturas sin clasificar.
  - `get_tax_obligations` — cruza `tax_obligations` (Fase 4) con horizonte de días.
  - `get_missing_documents` — meses del año sin ninguna factura.
  - `search_document` — por número, NIT o nombre del proveedor.
  - `escalate_to_human` — marca `conversations.status = 'escalated'`.
- `backend/app/agent/loop.py` — tool-use loop con Sonnet 5, `MAX_ITERS=10`, system prompt en español, persiste cada turno (`user`/`assistant`/`tool`) en `messages` con tokens y latencia. Si no hay `ANTHROPIC_API_KEY` responde fallback amistoso y escala.
- `backend/app/agent/routes.py` — `POST /agent/message`:
  - Identifica cliente por `phone` (últimos 10 dígitos, se normaliza) o `client_id`.
  - Reabre conversación por `(channel, external_id)` o toma la última activa.
  - Persiste el mensaje del usuario, corre el loop, devuelve `text` listo para enviar.
- `backend/app/notifications/whatsapp.py` — `send_text(phone, text)` via Evolution API. Si no hay credenciales, devuelve `{ok: False, reason: 'evolution_not_configured'}` (log-only, útil para tests).
- `backend/app/notifications/reminders.py` — `run_reminders()`: agrupa obligaciones `pending` con `due_date` a 5/2/0 días, envía un solo WhatsApp por cliente con el detalle.
- `backend/app/notifications/routes.py` — `POST /notifications/reminders/run` (autenticado con header `x-cron-secret = INGEST_EMAIL_SECRET`) + preview autenticado por JWT para staff.
- `backend/app/ingest/whatsapp.py` — el webhook de Evolution ahora también atiende mensajes de texto: los deriva al agente y responde por WhatsApp.

### Flujos n8n (`n8n/flows/`)

- `whatsapp-ingest.json` — pass-through de Evolution → backend `/webhooks/evolution` (respeta `x-signature`).
- `tax-reminders.json` — cron `0 8 * * *` (America/Bogota) → `POST /notifications/reminders/run` con `x-cron-secret`.
- `monthly-reports.json` — placeholder para Fase 6.
- `n8n/README.md` — variables requeridas (`API_BASE`, `CRON_SECRET`, `EVOLUTION_WEBHOOK_SECRET`) y cómo importar.

## Contrato del endpoint

```
POST /agent/message
{
  "phone": "+573001112233",      // o "client_id": "uuid"
  "channel": "whatsapp",
  "external_id": "573001112233@s.whatsapp.net",
  "message": "¿cuánto debo de IVA?"
}
→ 200
{
  "text": "Tu IVA jul-ago 2026 es $1.200.000, vence el 08 nov 2026 (en 5 días).",
  "conversation_id": "uuid",
  "escalated": false,
  "tools_called": ["get_tax_obligations"],
  "iterations": 2,
  "tokens_in": 850,
  "tokens_out": 120,
  "latency_ms": 1420
}
```

## Idempotencia y garantías

- Cada llamada persiste user + assistant + tool_results en `messages`. Reejecutar la misma pregunta crea un nuevo turno (correcto: no queremos deduplicar preguntas humanas).
- El loop tiene tope duro (`MAX_ITERS=10`). Si el modelo insiste en tools sin cerrar → escala automático.
- Anthropic caído → mensaje amigable + escala. `send_text` sin credenciales → log-only, no revienta.
- El agente **nunca** cruza clientes: todas las tools filtran por `client_id` del contexto.

## Tests (12 nuevos, total repo: 72)

- Schemas Anthropic válidos (5 tools).
- Cada tool contra un `FakeSupabase` in-memory:
  - obligaciones pending dentro del horizonte,
  - documentos pendientes + facturas sin clasificar,
  - meses sin facturas,
  - búsqueda por proveedor,
  - escalamiento actualiza `conversations.status`.
- Loop con Anthropic mockeado:
  - flujo tool_use → text final,
  - sin API key → escalación amistosa,
  - loop infinito → corta en `MAX_ITERS`.
- Reminders:
  - agrupa correctamente y llama `send_text`,
  - salta clientes sin teléfono.

## Deuda / decisiones pendientes

- **Evolution credentials**: `EVOLUTION_API_URL/API_KEY/INSTANCE_NAME` siguen sin poblar en `.env`. Sin ellas, el envío no sale pero el resto del pipeline funciona. Config del webhook Hostinger queda para Fase 8 (deploy).
- **Prior turns**: se traen los últimos 8 mensajes user/assistant con `content` en texto plano. Los turnos previos con tool_use no se rehidratan (sería mezcla frágil de bloques); si el modelo necesita re-consultar, llama de nuevo la tool. Aceptable para WhatsApp.
- **Deduplicación de recordatorios**: si el cron se corre 2 veces el mismo día, el cliente recibe el mensaje dos veces. Cuando pese, agregar tabla `reminder_sent(client_id, obligation_id, date)`.
- **Rate limit del agente**: no hay tope por cliente/hora. Para producción real, agregar como en ingesta.
- **Formato de moneda**: se hace en `agent/tools.py` con `_cop` (locale-agnostic `1.234.567`). Cuando se pluralicen destinos (email, web) mover a `app/formatters/`.
- **`monthly-reports.json`**: sólo scaffolding — la Fase 6 debe rellenar el nodo `TODO` con la generación por cliente activo.

## Comandos útiles

```bash
cd backend && source .venv/bin/activate

# Tests
python -m pytest tests/test_agent.py -v

# Probar el agente end-to-end (necesita ANTHROPIC_API_KEY y un cliente con teléfono)
curl -X POST "$API/agent/message" -H "content-type: application/json" \
  -d '{"phone":"+573001112233","channel":"whatsapp","message":"¿qué facturas tengo pendientes?"}'

# Disparar recordatorios manualmente (simula el cron n8n)
curl -X POST "$API/notifications/reminders/run" \
  -H "x-cron-secret: $INGEST_EMAIL_SECRET"

# Preview autenticado (staff)
curl -X POST "$API/notifications/reminders/preview" \
  -H "Authorization: Bearer $JWT"
```
