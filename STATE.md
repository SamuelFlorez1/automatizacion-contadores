# Estado actual del proyecto

**Última actualización**: 2026-09-26
**Fase actual**: Fase 0 cerrada ✅ — próxima sesión arranca **Fase 1**
**Última sesión**: Fase 0 completa (scaffold backend + frontend + docker + docs)

---

## ¿En qué vamos?

**Fase 0 cerrada.** Ver `docs/phases/phase-0.md` para bitácora completa.

**Bloqueador antes de Fase 1**: el usuario debe crear el proyecto Supabase (`sa-east-1`) y llenar en `.env`:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_JWT_SECRET`

## Próximo paso concreto — arrancar Fase 1

Al abrir sesión nueva:

1. Confirmar con el usuario que Supabase está creado y `.env` está lleno.
2. Correr smoke test de Fase 0 primero (opcional pero recomendado):
   - `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && pytest`
   - `uvicorn app.main:app --reload` → `curl localhost:8000/health`
3. Empezar Fase 1:
   - `backend/migrations/0001_init.sql` con el schema completo del §5 del spec original
   - `backend/app/db/client.py` (cliente Supabase)
   - Buscar en web y cablear:
     - `backend/app/tax/calendar_2026.json` (calendario DIAN 2026 — IVA bimestral/cuatrimestral, ReteFuente, ICA, renta, régimen Simple)
     - `backend/app/tax/puc.json` (catálogo PUC resumido — cuentas más usadas para servicios y comercio)
   - `backend/seeds/seed.py`: 1 despacho, 2 clientes (Simple + Ordinario USD), 20–30 facturas/cliente, 3 meses
   - Generadores: XMLs UBL 2.1 sintéticos, CSVs bancarios coherentes, imágenes/PDFs de facturas
   - Configurar Auth Supabase con roles: `firm_admin`, `accountant`, `client`
4. Cerrar Fase 1 actualizando este archivo, `PLAN.md`, y creando `docs/phases/phase-1.md`.

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md          # contexto general
cat STATE.md           # este archivo (dónde vamos)
cat PLAN.md            # plan completo
cat DECISIONS.md       # decisiones tomadas
ls docs/phases/        # fases cerradas con bitácora
git log --oneline -20  # últimos commits
```

## Bloqueos / esperando algo

- **Fase 1**: usuario debe crear proyecto Supabase antes de que se puedan correr migraciones remotas. Se puede desarrollar el schema y probar contra Postgres local (`docker compose up -d db`) mientras tanto.
- **Fase 5**: usuario tiene Evolution API en Hostinger; pedirá URL/key/instance cuando llegue el momento.

## Cambios recientes

- 2026-09-26: Fase 0 completa — scaffold monorepo (backend FastAPI, frontend Next 15, Postgres local, Dockerfile, README, sistema de contexto). Ver `docs/phases/phase-0.md`.
