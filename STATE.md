# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 7 cerrada ✅ — próxima sesión arranca **Fase 8 (Deploy + polish)**
**Última sesión**: Fase 7 completa — dashboard Next 15 con auth Supabase, layout despacho, listado y detalle de clientes, conciliación, reportes con descarga PDF y upload manual. `pnpm build` limpio.

---

## ¿En qué vamos?

**Fase 7 cerrada.** Ver `docs/phases/phase-7.md`. Rutas nuevas en `frontend/app/`:
- `/login` — Supabase Auth (email+password).
- `/clients` — listado.
- `/clients/[id]` — resumen (facturas + movimientos + obligaciones).
- `/clients/[id]/reconciliation` — matches y pendientes, corre `POST /bank/reconcile/{cid}`.
- `/clients/[id]/reports` — descarga PDFs Fase 6 con Bearer JWT.
- `/clients/[id]/upload` — `POST /ingest/upload` y `POST /bank/upload`.

**Middleware** (`frontend/middleware.ts`) refresca cookies y redirige a `/login` cualquier ruta protegida.

## Próximo paso concreto — arrancar Fase 8 (Deploy + polish)

1. Backend a **Railway**:
   - Dockerfile con `apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi8 fonts-liberation` (WeasyPrint).
   - Env vars: Anthropic, Supabase (URL/service/anon/JWT_SECRET), Evolution (si hay), INGEST_*, `APP_ENV=production`.
   - Cambiar `allow_origins` de `*` a lista blanca con el dominio Vercel.
2. Frontend a **Vercel**:
   - Env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` (URL Railway).
3. Webhook Evolution → apuntar a URL Railway (`/webhooks/evolution` — ver Fase 2/5).
4. Healthcheck `/health` en Railway.
5. GitHub Actions: workflow que corre `pytest` (backend) + `pnpm typecheck && pnpm build` (frontend) en push a main.
6. README final con: setup local, seed, cómo abrir la demo desplegada, credenciales demo.
7. `git init remote origin`, push a GitHub público.
8. Cerrar STATE/PLAN/phase-8.md + commit `feat(phase-8)`.

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md STATE.md PLAN.md DECISIONS.md
ls docs/phases/
git log --oneline -20
```

## Bloqueos / esperando algo

- **Evolution**: sin credenciales; envío WhatsApp queda log-only.
- **Deuda tax**: Renta PJ/GC y declaración anual Simple siguen sin calcular.
- **CORS**: `app.main` sigue con `allow_origins=["*"]` en dev; ajustar en Fase 8.
- **Sin tests en frontend**: por convención del proyecto (solo módulos fiscales críticos).

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 7 completa.** Frontend Next 15 con Supabase Auth (SSR), middleware de sesión, dashboard despacho (sidebar+topbar), listado y detalle de clientes (facturas/bancos/obligaciones), vista de conciliación con botón que corre el motor, descarga de PDFs de Fase 6 y upload manual de documentos y CSVs. `pnpm build` limpio (8 rutas). Bitácora: `docs/phases/phase-7.md`.
- 2026-09-28: **Fase 6 completa.** Reportes mensual y Formulario 300 PDF, narrativa Sonnet 5 con fallback, endpoints `/reports/*`, n8n mensual cableado, 13 tests nuevos (85 total).
- 2026-09-28: **Fase 5 completa.** Agente WhatsApp (5 tools + Sonnet loop, `MAX_ITERS=10`), `/agent/message`, envío Evolution, cron `/notifications/reminders/run`, 3 flujos n8n exportados. 12 tests nuevos (72 total).
- 2026-09-28: **Fase 4 completa.** IVA/rete_fuente/rete-ICA/ICA Bogotá/Simple, generador idempotente de `tax_obligations`, endpoints `/tax/*`. 17 tests nuevos (60 total).
- 2026-09-28: **Fase 3 completa.** Clasificación PUC (Haiku + reglas), deducibilidad E.T., parser CSV, motor conciliación. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS.
- 2026-09-28: **Fase 1 completa.** Schema SQL, seed real, calendario DIAN 2026, PUC, usuarios demo.
- 2026-09-26: Fase 0 completa — scaffold monorepo.
