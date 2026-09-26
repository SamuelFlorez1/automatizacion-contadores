# Fase 0 — Fundación

**Cerrada**: 2026-09-26
**Sesión(es)**: 1

## Qué se construyó

**Raíz**
- `CLAUDE.md`, `PLAN.md`, `STATE.md`, `DECISIONS.md` — sistema de contexto local
- `.gitignore`, `.env.example`
- `README.md` con setup completo
- `docker-compose.yml` con servicio `db` (Postgres 16) y perfil `full` para `api`
- `docs/phases/README.md` con plantilla

**Backend (`backend/`)**
- `pyproject.toml` con deps: FastAPI, Anthropic, Supabase, lxml, pdfplumber, pandas, WeasyPrint, structlog, pytest, ruff, mypy
- `app/main.py` con FastAPI + `/health` + `/`
- `app/config.py` con `Settings` (Pydantic Settings) leyendo desde `.env`
- `Dockerfile` con libs nativas para WeasyPrint y lxml
- `tests/test_health.py` smoke

**Frontend (`frontend/`)**
- `package.json` con Next 15 + React 19 RC + Tailwind + Supabase SSR + shadcn deps base
- `tsconfig.json`, `next.config.mjs`, `postcss.config.mjs`, `tailwind.config.ts`, `.eslintrc.json`
- `app/layout.tsx`, `app/page.tsx`, `app/globals.css` mínimos

## Decisiones locales

- No corrí `pip install` ni `pnpm install` en esta sesión — instalación queda para la próxima cuando el usuario tenga Supabase creado y quiera correr en local. Sirve como validación de arranque de Fase 1.
- Modelos configurados por env (`MODEL_SONNET`, `MODEL_HAIKU`) para poder cambiar sin recompilar.
- El servicio `api` en `docker-compose.yml` está detrás del perfil `full` para no forzar el build cada vez que solo se quiera Postgres local.
- React 19 RC porque Next 15 lo pide.

## Comandos útiles

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest

# Frontend
cd frontend
pnpm install     # o npm install
pnpm dev

# Docker (solo Postgres)
docker compose up -d db

# Docker (stack completo)
docker compose --profile full up
```

## Gotchas

- Python 3.13 está en la máquina; `pyproject.toml` pide `>=3.11`. Debería funcionar, pero si alguna dep falla, bajar a 3.11 o 3.12.
- WeasyPrint necesita libs nativas del sistema (`libpango`, `libcairo`, etc.) — el Dockerfile ya las incluye; para desarrollo local en macOS: `brew install pango cairo gdk-pixbuf libffi`.
- CORS abierto (`*`) solo en `development`; cambiar antes de deploy a producción.

## Deuda dejada

- No hay migraciones SQL todavía (Fase 1).
- No hay cliente Supabase (`backend/app/db/client.py`) — se crea en Fase 1.
- No hay lockfile del frontend — se genera al primer `pnpm install`.
- Auth Supabase queda para Fase 1 junto con el schema.

## Smoke test

1. `cp .env.example .env` y llenar (aunque sea con valores dummy para local).
2. `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` — debe instalar sin errores.
3. `uvicorn app.main:app --reload` — arranca.
4. `curl localhost:8000/health` → `{"status":"ok","env":"development","timezone":"America/Bogota"}`.
5. `pytest` → dos tests pasan.
6. `cd frontend && pnpm install && pnpm dev` → abre `http://localhost:3000` y ve la página "Despacho Contable — Fase 0".
