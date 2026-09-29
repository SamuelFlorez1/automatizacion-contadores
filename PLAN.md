# Plan maestro — Despacho Contable Automatizado

Fases secuenciales. Cada fase = una sesión ideal de Claude Code. No pasamos a la siguiente hasta que la anterior corra end-to-end.

Formato: `[ ]` pendiente, `[~]` en curso, `[x]` hecho, `[!]` bloqueado.

---

## Fase 0 — Fundación ✅

- [x] `git init` + estructura de carpetas
- [x] `CLAUDE.md`, `PLAN.md`, `STATE.md`, `DECISIONS.md`
- [x] `.gitignore`, `.env.example`
- [x] `backend/pyproject.toml` con dependencias (FastAPI, Anthropic, Supabase, pandas, lxml, pdfplumber, weasyprint, pytest)
- [x] `backend/app/main.py` con FastAPI mínimo + healthcheck
- [x] `backend/app/config.py` (Pydantic Settings desde env)
- [x] `docker-compose.yml` con Postgres local
- [ ] Crear proyecto Supabase en `sa-east-1` (usuario lo hace, guarda claves en `.env`) — **acción del usuario, pendiente**
- [x] `frontend/` con Next.js 15 + TypeScript + Tailwind + shadcn/ui inicializado
- [x] `README.md` con instrucciones de setup local
- [x] Primer commit

**Entrega**: `docker compose up` levanta Postgres; `uvicorn app.main:app` responde `/health`; `pnpm dev` levanta Next con página vacía. Bitácora: `docs/phases/phase-0.md`.

---

## Fase 1 — Modelo de datos + seed ✅

- [x] Migraciones SQL en `backend/migrations/` (schema completo con RLS por firm_id)
- [x] Cliente Supabase (`backend/app/db/client.py`)
- [x] Buscar y cablear **calendario DIAN 2026** → `backend/app/tax/calendar_2026.json`
- [x] Buscar y cablear **catálogo PUC** resumido → `backend/app/tax/puc.json`
- [x] Script `backend/seeds/seed.py`:
  - 1 despacho
  - Cliente A: Régimen Simple, servicios
  - Cliente B: Régimen Ordinario con importaciones USD
  - 25 + 28 facturas, 3 meses (jul-sep 2026)
- [x] Generador XMLs UBL 2.1 sintéticos válidos
- [x] Generador CSVs bancarios coherentes con facturas
- [x] Generador imágenes PNG de facturas sintéticas (para Vision — ~15% del volumen)
- [x] Auth Supabase configurada con roles: `firm_admin`, `accountant`, `client`

**Entrega**: `python -m seeds.seed` + `python -m seeds.seed_users` pueblan la base. Archivos en `backend/seeds/invoices_xml/`, `backend/seeds/invoices_images/`, `backend/seeds/bank_statements/`. Bitácora: `docs/phases/phase-1.md`.

---

## Fase 2 — Extracción ✅

- [x] `extraction/xml_ubl.py`: parser DIAN con validación
- [x] `extraction/validators.py`: NIT (dígito verificación), CUFE, hash duplicados
- [x] `extraction/vision.py`: Claude Vision con prompt estructurado + retorno JSON
- [x] `ingest/whatsapp.py`, `ingest/email.py`, `ingest/upload.py` con idempotencia
- [x] Firma HMAC en webhook Evolution
- [x] Tests: parser XML, validador NIT, CUFE
- [x] Rate limit por cliente/día (config)

**Entrega**: subir imagen/PDF/XML por endpoint deja documento en DB con todos los campos extraídos. Bitácora: `docs/phases/phase-2.md`.

---

## Fase 3 — Clasificación + Conciliación ✅

- [x] `classification/puc.py`: Haiku 4.5 con catálogo PUC como contexto → cuenta sugerida (+ reglas offline como fallback)
- [x] `classification/deductibility.py`
- [x] `reconciliation/csv_parser.py` + `reconciliation/engine.py`: exact (con tolerancia a retenciones), fuzzy, transferencias internas
- [x] Endpoint `POST /bank/upload` (CSV → normalización → matching) + `/bank/reconcile/{cid}` + `/invoices/{id}/classify` + `/clients/{cid}/classify`
- [x] Score de confianza por match
- [x] Tests: motor de conciliación (14) + clasificación (10). Total repo: 43.

**Entrega**: subir CSV bancario devuelve JSON con matches automáticos + revisiones pendientes. Bitácora: `docs/phases/phase-3.md`.

---

## Fase 4 — Cálculo fiscal ✅

- [x] `tax/iva.py`: bimestral/cuatrimestral según régimen
- [x] `tax/rete_fuente.py`: por concepto (mapa PUC→concepto DIAN)
- [x] `tax/rete_ica.py`: por ciudad (Bogotá con tarifas por CIIU)
- [x] `tax/simple.py`: régimen unificado (grupo por CIIU, tramos UVT)
- [x] Generador `tax/obligations.py` UPSERT idempotente por (client_id, kind, period_label)
- [x] Endpoints `POST /tax/generate`, `GET /tax/calculate`, `GET /tax/obligations`
- [x] Tests: 17 (cálculos + generador). Total repo: 60.

**Entrega**: `/tax/calculate/{client_id}/{period}` devuelve obligaciones calculadas. Bitácora: `docs/phases/phase-4.md`.

---

## Fase 5 — Agente WhatsApp + n8n ✅

- [x] `agent/tools.py`: `get_pending_invoices`, `get_tax_obligations`, `get_missing_documents`, `search_document`, `escalate_to_human`
- [x] `agent/loop.py`: Claude Sonnet 5 tool-use loop (`MAX_ITERS=10`, persistencia por turno)
- [x] `POST /agent/message` — identifica cliente por teléfono, corre agente, guarda mensajes
- [x] `notifications/whatsapp.py`: envío vía Evolution (fallback log-only sin credenciales)
- [x] Flujos n8n exportados: `whatsapp-ingest.json`, `tax-reminders.json`, `monthly-reports.json`
- [x] Cron n8n dispara recordatorios de vencimiento (`POST /notifications/reminders/run`)
- [x] Webhook Evolution atiende texto → agente → responde (además del media de Fase 2)
- [x] Tests: 12 nuevos (schemas, tools, loop mockeado, reminders). Total repo: 72.

**Entrega**: cliente pregunta por WhatsApp → agente responde correcto usando datos reales; cron envía recordatorio de IVA próximo a vencer. Bitácora: `docs/phases/phase-5.md`.

---

## Fase 6 — Reportes PDF ✅

- [x] `reports/monthly.py`: estado resultados, flujo caja, top 10 gastos, comparativo, análisis IA (Sonnet + fallback)
- [x] Templates HTML + WeasyPrint (`_base.html`, `monthly.html`, `iva_form300.html`)
- [x] `reports/iva_form300.py`: prellenado formato 300 (10 casillas)
- [x] `GET /reports/monthly/{client_id}/{period}` y `/reports/iva/{client_id}/{period_label}`
- [x] n8n `monthly-reports.json` cablead con cron mensual real
- [x] Tests: 13 nuevos (builders + render E2E con skip si faltan libs). Total repo: 85.

**Entrega**: `GET /reports/monthly/{cid}/2026-07` devuelve PDF; `GET /reports/iva/{cid}/jul-ago-2026` prellenado del 300. Bitácora: `docs/phases/phase-6.md`.

---

## Fase 7 — Frontend Next.js ✅

- [x] Auth con Supabase (login/logout, sesión) — `@supabase/ssr` + middleware
- [x] Layout despacho — sidebar + topbar con rol
- [x] Vista lista de clientes — `/clients`
- [x] Vista cliente: facturas, movimientos, obligaciones — `/clients/[id]`
- [x] Vista conciliación (matches + revisiones) — botón corre `/bank/reconcile`
- [x] Vista reportes (descarga PDF) — mensual + Formulario 300
- [x] Upload manual documentos + CSVs — `/ingest/upload` + `/bank/upload`

**Entrega**: `pnpm dev` abre dashboard; login con seed users → recorre toda la demo. `pnpm build` limpio. Bitácora: `docs/phases/phase-7.md`.

---

## Fase 8 — Deploy + polish final

- [ ] Backend a Railway
- [ ] Frontend a Vercel
- [ ] Variables de entorno en ambos
- [ ] Webhook Evolution apuntando a Railway
- [ ] Healthchecks
- [ ] GitHub Actions básico (lint + tests)
- [ ] README final claro
- [ ] Repo público en GitHub

**Entrega**: dominio Vercel abre la demo funcional; API Railway responde webhooks reales de WhatsApp.
