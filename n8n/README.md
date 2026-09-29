# Flujos n8n — Fase 5

Estos JSON se importan en el n8n self-hosted (Hostinger). Cada uno referencia
credenciales por nombre (no llevan secretos embebidos): configúralas en n8n
antes de activar el flujo.

## Variables de n8n necesarias

- `API_BASE`: URL pública del backend (ej. `https://api.despacho.example.com`).
- `CRON_SECRET`: valor de `INGEST_EMAIL_SECRET` del backend (reusado como
  shared secret para endpoints de cron).
- `EVOLUTION_WEBHOOK_SECRET`: mismo valor que en el backend (para firmar el
  reenvío del webhook de Evolution).

## Flujos

### 1. `whatsapp-ingest.json`
Recibe el webhook de Evolution API en n8n, lo reenvía a
`POST {API_BASE}/webhooks/evolution` **respetando el header `x-signature`**
(pass-through). Es un flujo pass-through mínimo — la lógica vive en el backend
(dedupe, extracción de adjuntos, agente conversacional para texto).

Ventaja de este intermediario: n8n puede logear, disparar alertas y reintentar
si el backend está caído.

### 2. `tax-reminders.json`
Cron diario a las 8:00 America/Bogota. Hace `POST {API_BASE}/notifications/reminders/run`
con `x-cron-secret: {CRON_SECRET}`. El backend agrupa obligaciones que vencen
en 5/2/0 días y despacha WhatsApp por cliente.

### 3. `monthly-reports.json`
Placeholder de Fase 6: el 1er día hábil del mes, dispara la generación de
reportes mensuales por cliente (`POST /reports/monthly/{client_id}/{period}`).
Actualmente el endpoint no existe (Fase 6) — el flujo está exportado como
plantilla lista para activar cuando la Fase 6 cierre.
