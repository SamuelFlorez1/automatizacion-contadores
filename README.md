# Despacho Contable Automatizado

Demo end-to-end de un sistema que automatiza la operación de un despacho contable colombiano: ingesta de facturas por WhatsApp/email, extracción con IA, conciliación bancaria, agente conversacional y reportes.

**No es producción real** — es una demo pública construida para verse como producción, con datos sintéticos.

---

## Stack

- **Backend**: Python 3.11 + FastAPI + Anthropic Claude + Supabase
- **Frontend**: Next.js 15 + TypeScript + Tailwind + shadcn/ui
- **DB**: Supabase (Postgres) — región `sa-east-1`
- **Orquestación**: n8n (Hostinger self-hosted)
- **WhatsApp**: Evolution API (Hostinger self-hosted)
- **Deploy**: Railway (backend) + Vercel (frontend)

---

## Setup local

### 1. Clonar y variables de entorno

```bash
git clone <repo>
cd "Automatizacion contadores"
cp .env.example .env
# Editar .env con las claves reales (ver más abajo)
```

Variables mínimas para arrancar Fase 0:
- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`

Evolution API y n8n solo se necesitan a partir de la Fase 5.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Debe responder en `http://localhost:8000/health` con `{"status": "ok", ...}`.

### 3. Postgres local (opcional; puedes usar Supabase remoto directamente)

```bash
docker compose up -d db
```

### 4. Frontend

```bash
cd frontend
pnpm install    # o npm install
pnpm dev
```

Debe abrir en `http://localhost:3000`.

### 5. Stack completo con Docker

```bash
docker compose --profile full up
```

---

## Cómo se organiza el trabajo

El proyecto se construye por **fases**, una fase = una sesión de Claude Code. Lee siempre en este orden al iniciar sesión:

1. `CLAUDE.md` — reglas y contexto
2. `STATE.md` — dónde vamos y próximo paso
3. `PLAN.md` — fases y checkboxes
4. `DECISIONS.md` — decisiones tomadas
5. `docs/phases/phase-N.md` — bitácora por fase cerrada

---

## Estructura

```
.
├── backend/           API Python (FastAPI)
├── frontend/          Dashboard Next.js
├── n8n/               Flujos exportados
├── docs/phases/       Bitácora por fase
├── CLAUDE.md          Contexto para Claude Code
├── PLAN.md            Plan por fases
├── STATE.md           Estado actual
└── DECISIONS.md       Log de decisiones
```

---

## Licencia

TBD.
