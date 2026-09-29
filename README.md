# Despacho Contable Automatizado

Demo end-to-end de un sistema que automatiza la operación de un despacho contable colombiano: ingesta de facturas (WhatsApp / email / upload), extracción con IA (Claude), clasificación PUC, conciliación bancaria, cálculo fiscal, agente conversacional y reportes PDF.

**No es producción real** — es una demo pública con datos sintéticos que se ve y funciona como producción.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11 · FastAPI · Pydantic v2 |
| Frontend | Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui |
| Base de datos | Supabase (Postgres) — `sa-east-1` |
| IA | Anthropic Claude (Sonnet 5 + Haiku 4.5) |
| Orquestación | n8n self-hosted |
| WhatsApp | Evolution API self-hosted |
| Deploy | Railway (backend) · Vercel (frontend) |

---

## Demo desplegada

| Servicio | URL |
|---|---|
| Frontend | _Pendiente — configurar en Vercel_ |
| API | _Pendiente — configurar en Railway_ |

### Credenciales demo

| Rol | Email | Password |
|---|---|---|
| Administrador | `admin@despachodemo.co` | `DemoAdmin2026!` |
| Contador | `contador@despachodemo.co` | `DemoConta2026!` |
| Cliente (Andina) | `andina@clientedemo.co` | `DemoAndi2026!` |
| Cliente (Pacífico) | `pacifico@clientedemo.co` | `DemoPaci2026!` |

---

## Setup local

### 1. Clonar y variables de entorno

```bash
git clone <repo>
cd "Automatizacion contadores"
cp .env.example .env
# Editar .env con claves reales
```

Variables mínimas: `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Healthcheck: `http://localhost:8000/health`

### 3. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Abre en `http://localhost:3000`.

### 4. Seed (datos demo)

Requiere Supabase configurado:

```bash
cd backend
python -m seeds.seed          # datos: despacho, clientes, facturas, movimientos
python -m seeds.seed_users    # usuarios de autenticación
```

### 5. Tests

```bash
cd backend
pytest -x -q        # 85 tests
```

```bash
cd frontend
pnpm exec tsc --noEmit   # type check
pnpm build                # build completo
```

---

## Deploy

### Backend → Railway

1. Conectar repo en Railway, seleccionar root path `backend/`.
2. Railway detecta el `Dockerfile` automáticamente.
3. Variables de entorno requeridas:

| Variable | Valor |
|---|---|
| `APP_ENV` | `production` |
| `ANTHROPIC_API_KEY` | Tu clave Anthropic |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key |
| `SUPABASE_ANON_KEY` | Anon key |
| `CORS_ORIGINS` | `https://tu-app.vercel.app` |
| `EVOLUTION_API_URL` | _(opcional)_ URL Evolution |
| `EVOLUTION_API_KEY` | _(opcional)_ API key Evolution |
| `EVOLUTION_INSTANCE_NAME` | _(opcional)_ instancia |
| `EVOLUTION_WEBHOOK_SECRET` | _(opcional)_ HMAC secret |

4. Railway asigna un dominio → usarlo como `NEXT_PUBLIC_API_URL` en Vercel.

### Frontend → Vercel

1. Importar repo, seleccionar root directory `frontend/`.
2. Framework preset: Next.js.
3. Variables de entorno:

| Variable | Valor |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | URL del proyecto Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key |
| `NEXT_PUBLIC_API_URL` | URL Railway (e.g. `https://xxx.railway.app`) |

### Webhook WhatsApp

Apuntar Evolution API webhook a: `https://<railway-domain>/webhooks/evolution`

---

## Estructura del proyecto

```
.
├── backend/              API Python (FastAPI)
│   ├── app/
│   │   ├── agent/        Agente conversacional WhatsApp
│   │   ├── classification/  Clasificación PUC (Haiku + reglas)
│   │   ├── extraction/   Parser UBL, Vision, validadores
│   │   ├── ingest/       Canales: WhatsApp, email, upload
│   │   ├── notifications/  Recordatorios y envío WhatsApp
│   │   ├── reconciliation/  Motor de conciliación bancaria
│   │   ├── reports/      Reportes PDF (WeasyPrint)
│   │   └── tax/          Cálculos fiscales colombianos
│   ├── migrations/       Schema SQL
│   ├── seeds/            Datos sintéticos
│   └── tests/            85 tests
├── frontend/             Dashboard Next.js
│   ├── app/              Rutas (login, clients, reports...)
│   ├── components/       UI components
│   └── lib/              Supabase client, API helpers
├── n8n/                  Flujos exportados
├── docs/phases/          Bitácora por fase
└── .github/workflows/    CI (lint + tests + build)
```

---

## Fases del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Fundación — scaffold monorepo | ✅ |
| 1 | Modelo de datos + seed | ✅ |
| 2 | Extracción (UBL, Vision, ingesta) | ✅ |
| 3 | Clasificación PUC + conciliación bancaria | ✅ |
| 4 | Cálculo fiscal (IVA, retenciones, Simple) | ✅ |
| 5 | Agente WhatsApp + n8n | ✅ |
| 6 | Reportes PDF (mensual + Form 300) | ✅ |
| 7 | Frontend Next.js (dashboard completo) | ✅ |
| 8 | Deploy + polish | ✅ |

---

## Licencia

MIT
