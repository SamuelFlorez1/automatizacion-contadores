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

## Fase 3 — Clasificación + Conciliación

- [ ] `classification/puc.py`: Haiku 4.5 con catálogo PUC como contexto → cuenta sugerida
- [ ] `classification/deductibility.py`
- [ ] `reconciliation/engine.py` con pandas: exact match, fuzzy, transferencias internas
- [ ] Endpoint `/bank/upload` (CSV → normalización → matching)
- [ ] Score de confianza por match
- [ ] Tests: motor de conciliación

**Entrega**: subir CSV bancario devuelve JSON con matches automáticos + revisiones pendientes.

---

## Fase 4 — Cálculo fiscal

- [ ] `tax/iva.py`: bimestral/cuatrimestral según régimen
- [ ] `tax/rete_fuente.py`: por concepto
- [ ] `tax/rete_ica.py`: por ciudad configurable
- [ ] `tax/simple.py`: régimen unificado
- [ ] Generador de `tax_obligations` desde facturas + calendario DIAN
- [ ] Tests: cálculos fiscales

**Entrega**: `/tax/calculate/{client_id}/{period}` devuelve obligaciones calculadas.

---

## Fase 5 — Agente WhatsApp + n8n

- [ ] `agent/tools.py`: `get_pending_invoices`, `get_tax_obligations`, `get_missing_documents`, `search_document`, `escalate_to_human`
- [ ] `agent/loop.py`: Claude Sonnet 5 tool-use loop
- [ ] `POST /agent/message` — identifica cliente por teléfono, corre agente, guarda mensajes
- [ ] `notifications/whatsapp.py`: envío vía Evolution
- [ ] Flujos n8n exportados: `whatsapp-ingest.json`, `tax-reminders.json`, `monthly-reports.json`
- [ ] Cron n8n dispara recordatorios de vencimiento

**Entrega**: cliente pregunta por WhatsApp → agente responde correcto usando datos reales; cron envía recordatorio de IVA próximo a vencer.

---

## Fase 6 — Reportes PDF

- [ ] `reports/monthly.py`: estado resultados, flujo caja, top 10 gastos, comparativo, análisis IA
- [ ] Templates HTML + WeasyPrint
- [ ] `reports/iva_form300.py`: prellenado formato 300
- [ ] `GET /reports/monthly/{client_id}/{period}` y `/reports/iva/{client_id}/{period}`

**Entrega**: descargar PDFs desde dashboard.

---

## Fase 7 — Frontend Next.js

- [ ] Auth con Supabase (login/logout, sesión)
- [ ] Layout despacho
- [ ] Vista lista de clientes
- [ ] Vista cliente: facturas, movimientos, obligaciones
- [ ] Vista conciliación (matches + revisiones)
- [ ] Vista reportes (descarga PDF)
- [ ] Upload manual documentos + CSVs

**Entrega**: recorrer toda la demo desde el navegador sin tocar la API directamente.

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
