# Fase 8 — Deploy + polish final

**Fecha**: 2026-09-28
**Estado**: ✅ Completa

## Qué se construyó

### Dockerfile (mejorado)
- Agregado `fonts-liberation` (WeasyPrint necesita fuentes TrueType para renderizar PDFs)
- Agregado `libpangocairo-1.0-0` (dependencia faltante de WeasyPrint)
- HEALTHCHECK integrado que prueba `/health` cada 30s
- Cambiado `pip install -e .` → `pip install .` (no necesita modo editable en producción)

### CORS production-ready
- `app/config.py`: nuevo campo `cors_origins` (string comma-separated)
- `app/main.py`: en `development` acepta localhost:3000 + los orígenes extra de `CORS_ORIGINS`; en `production` solo acepta `CORS_ORIGINS`

### Railway config
- `backend/railway.toml` con builder Dockerfile, healthcheck en `/health`
- `backend/.dockerignore` excluye tests, seeds, venv, .env

### GitHub Actions CI
- `.github/workflows/ci.yml`:
  - **backend**: `ruff check` + `pytest`
  - **frontend**: `tsc --noEmit` + `pnpm build`
  - Se corre en push/PR a `main`

### `.env.example`
- Agregado `CORS_ORIGINS` con ejemplo

### README final
- Stack, credenciales demo, setup local, instrucciones de deploy (Railway + Vercel), estructura del proyecto, tabla de fases

## Variables de entorno para deploy

### Railway (backend)
- `APP_ENV=production`
- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`
- `CORS_ORIGINS=https://tu-app.vercel.app`
- `EVOLUTION_*` (opcionales, si hay instancia)

### Vercel (frontend)
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL=https://xxx.railway.app`

## Deuda técnica / notas

- 57 errores de ruff preexistentes (mayormente import sort y tipos) — no bloqueantes, tests pasan
- Evolution API sin credenciales: envío WhatsApp sigue en modo log-only
- Deploy real requiere que el usuario conecte Railway/Vercel a GitHub y configure env vars
- Licencia en README puesta como MIT — el usuario puede cambiarla
