# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 2 cerrada ✅ — próxima sesión arranca **Fase 3 (Clasificación + Conciliación)**
**Última sesión**: Fase 2 completa — extracción XML/Vision, ingesta por upload/WhatsApp/email con idempotencia, HMAC, rate limit y tests.

---

## ¿En qué vamos?

**Fase 2 cerrada.** Ver `docs/phases/phase-2.md`. Endpoints: `POST /ingest/upload` (JWT), `POST /webhooks/evolution` (HMAC), `POST /ingest/email` (secreto). 19 tests pasan.

**Base de datos remoto** (`flwxzcqggtefhxnxxfhy`): seed re-ejecutado (53 facturas, 61 docs, 4 usuarios demo); bucket privado `documents` en Storage creado por la ingesta.

**Credenciales en `.env`**: ✅ Anthropic, Supabase. ⏸️ Evolution / n8n (Fase 5). Nuevas opcionales: `INGEST_EMAIL_SECRET`, `EVOLUTION_WEBHOOK_SECRET` (vacías = esos canales rechazan todo).

## Próximo paso concreto — arrancar Fase 3

1. `backend/app/classification/puc.py`: Haiku 4.5 con `tax/puc.json` como contexto → `invoices.puc_account`, `classification_confidence`.
2. `classification/deductibility.py` → `is_deductible`.
3. `reconciliation/engine.py` (pandas): exact, fuzzy, transferencias internas; `reconciliation_matches`.
4. `POST /bank/upload`: CSV → normalización → matching. Los CSV subidos por `/ingest/upload` quedan `documents.kind='bank_statement'`, `status='received'`. CSVs del seed en `backend/seeds/bank_statements/`.
5. Tests del motor de conciliación. Cerrar fase con STATE/PLAN/phase-3.md.

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md STATE.md PLAN.md DECISIONS.md
ls docs/phases/
git log --oneline -20
```

## Bloqueos / esperando algo

- **Fase 5**: Evolution API / n8n credentials pendientes.
- **Deuda**: WeasyPrint no está instalado en el venv local (Fase 6 lo pedirá).

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS. Corregido bug de `nit_dv` (residuo 1).
- 2026-09-28: **Fase 1 completa.** Schema SQL aplicado a Supabase remoto; 53 facturas seed; calendario DIAN 2026 + PUC cableados; usuarios demo con roles vía Supabase Auth.
- 2026-09-28: `SUPABASE_DB_URL` cargada; migraciones se ejecutan directo con psycopg.
- 2026-09-26: Fase 0 completa — scaffold monorepo. Ver `docs/phases/phase-0.md`.
