# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 4 cerrada ✅ — próxima sesión arranca **Fase 5 (Agente WhatsApp + n8n)**
**Última sesión**: Fase 4 completa — módulo `tax/` con IVA, rete_fuente, rete/ICA Bogotá, Simple, generador de obligaciones idempotente y 3 endpoints. 60 tests pasan.

---

## ¿En qué vamos?

**Fase 4 cerrada.** Ver `docs/phases/phase-4.md`. Endpoints nuevos: `POST /tax/generate/{cid}`, `GET /tax/calculate/{cid}/{period}`, `GET /tax/obligations/{cid}`.

Smoke real contra Supabase: Andina (Simple) 12 obligaciones/año ~2.6M COP; Pacífico (Ordinario+agente ret.) 24 obligaciones/año ~17.8M COP. Los rows quedaron en `tax_obligations` porque son datos demo válidos que Fase 5/6 consumirán.

**Credenciales en `.env`**: ✅ Anthropic, Supabase. ⏸️ Evolution / n8n (arranca Fase 5).

## Próximo paso concreto — arrancar Fase 5

1. `agent/tools.py` — 5 tools: `get_pending_invoices`, `get_tax_obligations` (usa lo que Fase 4 dejó en DB), `get_missing_documents`, `search_document`, `escalate_to_human`.
2. `agent/loop.py` — tool-use loop con Sonnet 5 (`claude-sonnet-5`), context en español, límite de 10 iteraciones.
3. Endpoint `POST /agent/message`: identifica cliente por `phone`, corre agente, persiste `conversations` + `messages` con tokens/latencia.
4. `notifications/whatsapp.py`: envío vía Evolution API (obtener credenciales primero).
5. Flujos n8n en `n8n/flows/`: `whatsapp-ingest.json` (ya llega a `/webhooks/evolution` que existe desde Fase 2), `tax-reminders.json` (cron diario que consulta obligaciones vencidas a 5/2/0 días y manda WhatsApp), `monthly-reports.json` (placeholder para Fase 6).
6. Tests: agente responde con datos reales; formato de tools válido.
7. Cerrar con STATE/PLAN/phase-5.md + commit `feat(phase-5)`.

**Bloqueador que resolver primero**: obtener `EVOLUTION_BASE_URL`, `EVOLUTION_API_KEY` y `EVOLUTION_INSTANCE_ID` del usuario (Hostinger).

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md STATE.md PLAN.md DECISIONS.md
ls docs/phases/
git log --oneline -20
```

## Bloqueos / esperando algo

- **Fase 5**: Evolution API / n8n credentials pendientes en `.env`.
- **Deuda**: WeasyPrint no está instalado en el venv local (Fase 6 lo pedirá).
- **Deuda tax**: Renta PJ/GC y declaración anual Simple no se calculan aún — el calendario ya los tiene, se atacarán en Fase 6 con los reportes anuales.

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 4 completa.** IVA/rete_fuente/rete-ICA/ICA Bogotá/Simple, generador idempotente de `tax_obligations`, endpoints `/tax/*`. 17 tests nuevos (60 total).
- 2026-09-28: **Fase 3 completa.** Clasificación PUC (Haiku + reglas), deducibilidad E.T., parser CSV, motor conciliación. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS.
- 2026-09-28: **Fase 1 completa.** Schema SQL, seed real, calendario DIAN 2026, PUC, usuarios demo.
- 2026-09-26: Fase 0 completa — scaffold monorepo.
