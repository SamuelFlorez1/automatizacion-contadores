# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 8 cerrada ✅ — proyecto completo, listo para deploy
**Última sesión**: Fase 8 — Dockerfile mejorado, CORS production, railway.toml, GitHub Actions CI, README final

---

## ¿En qué vamos?

**Proyecto completo.** Las 8 fases están cerradas. El sistema cubre:
- Ingesta multi-canal (WhatsApp, email, upload) con extracción IA
- Clasificación PUC (Haiku + reglas)
- Conciliación bancaria automática
- Cálculo fiscal colombiano (IVA, retenciones, Simple)
- Agente conversacional WhatsApp (Sonnet 5 + 5 tools)
- Reportes PDF (mensual + Formulario 300)
- Dashboard Next.js con auth Supabase
- Deploy config (Railway + Vercel + CI)

## Para deploy (acciones del usuario)

1. **Crear repo en GitHub** y push:
   ```bash
   git remote add origin <url>
   git push -u origin main
   ```

2. **Railway**: conectar repo → root `backend/` → configurar env vars (ver README)
3. **Vercel**: importar repo → root `frontend/` → configurar env vars
4. **CORS_ORIGINS** en Railway → URL del dominio Vercel
5. **Evolution webhook** → `https://<railway>/webhooks/evolution`

## Bloqueos / pendientes

- **Evolution**: sin credenciales; envío WhatsApp queda log-only
- **Deuda tax**: Renta PJ/GC y declaración anual Simple sin calcular
- **57 errores ruff**: preexistentes (import sort, tipos), no bloqueantes
- **Licencia**: puesta como MIT en README, cambiar si aplica

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 8 completa.** Dockerfile con fonts-liberation + HEALTHCHECK, CORS production (`cors_origins`), railway.toml, .dockerignore, GitHub Actions CI (ruff + pytest + tsc + build), README final con instrucciones de deploy.
- 2026-09-28: **Fase 7 completa.** Frontend Next 15 con Supabase Auth, dashboard, clientes, conciliación, reportes, upload.
- 2026-09-28: **Fase 6 completa.** Reportes PDF (mensual + Form 300), narrativa Sonnet 5. 85 tests.
- 2026-09-28: **Fase 5 completa.** Agente WhatsApp, Evolution, cron recordatorios, n8n. 72 tests.
- 2026-09-28: **Fase 4 completa.** Cálculos fiscales colombianos. 60 tests.
- 2026-09-28: **Fase 3 completa.** Clasificación PUC + conciliación. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS.
- 2026-09-28: **Fase 1 completa.** Schema SQL, seed, calendario DIAN, PUC, usuarios demo.
- 2026-09-26: **Fase 0 completa.** Scaffold monorepo.
