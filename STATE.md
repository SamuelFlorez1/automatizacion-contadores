# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 6 cerrada ✅ — próxima sesión arranca **Fase 7 (Frontend Next.js)**
**Última sesión**: Fase 6 completa — reportes mensual y Formulario 300 en PDF, narrativa Sonnet con fallback, n8n mensual cablead. 85 tests pasan.

---

## ¿En qué vamos?

**Fase 6 cerrada.** Ver `docs/phases/phase-6.md`. Endpoints nuevos:
- `GET /reports/monthly/{client_id}/{YYYY-MM}` — PDF (o `?format=html`).
- `GET /reports/iva/{client_id}/{period_label}` — PDF del Formulario 300 prellenado.

**WeasyPrint**: `pip install weasyprint jinja2` + `brew install pango cairo gdk-pixbuf libffi` en macOS.
En local: correr con `DYLD_LIBRARY_PATH=/opt/homebrew/lib` (el pytest lo requiere para los 2 tests de render E2E).
En Railway (Fase 8): agregar `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi8` al build.

**Credenciales en `.env`**: ✅ Anthropic, Supabase. ⏸️ Evolution sigue pendiente (no bloquea Fase 7).

## Próximo paso concreto — arrancar Fase 7 (Frontend)

1. `frontend/` ya tiene Next 15 + TS + Tailwind + shadcn/ui inicializado (Fase 0). Verificar que `pnpm dev` levanta.
2. Cliente Supabase en el front (`@supabase/ssr`) con `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
3. Login/logout con email+password (usuarios seed de Fase 1). Middleware que redirige según rol.
4. Layout despacho: sidebar (clientes, conciliación, obligaciones, reportes), topbar con usuario.
5. Vista lista de clientes (`/clients`) — pega directo a Supabase con RLS.
6. Vista cliente (`/clients/[id]`) — facturas emitidas/recibidas, movimientos bancarios, obligaciones.
7. Vista conciliación (`/clients/[id]/reconciliation`) — matches + revisiones pendientes.
8. Vista reportes (`/clients/[id]/reports`) — botones que descargan PDFs Fase 6 (mensual + IVA).
9. Upload manual documentos + CSV — llama a `/documents/upload` y `/bank/upload` con JWT.
10. Cerrar STATE/PLAN/phase-7.md + commit `feat(phase-7)`.

**Nota**: los endpoints de reportes requieren JWT válido; el front debe pasarlo como `Authorization: Bearer`.

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md STATE.md PLAN.md DECISIONS.md
ls docs/phases/
git log --oneline -20
```

## Bloqueos / esperando algo

- **Evolution**: sin credenciales; envío WhatsApp queda log-only. No bloquea Fase 7.
- **Deuda tax**: Renta PJ/GC y declaración anual Simple siguen sin calcular. Se pueden atacar en paralelo a Fase 7 o dejarse para Fase 8.
- **Docker/Railway build para WeasyPrint**: hay que agregar apt packages cuando arranquemos Fase 8.

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 6 completa.** Reportes mensual y Formulario 300 PDF, narrativa Sonnet 5 con fallback, endpoints `/reports/*`, n8n mensual cableado, 13 tests nuevos (85 total).
- 2026-09-28: **Fase 5 completa.** Agente WhatsApp (5 tools + Sonnet loop, `MAX_ITERS=10`), `/agent/message`, envío Evolution, cron `/notifications/reminders/run`, 3 flujos n8n exportados. 12 tests nuevos (72 total).
- 2026-09-28: **Fase 4 completa.** IVA/rete_fuente/rete-ICA/ICA Bogotá/Simple, generador idempotente de `tax_obligations`, endpoints `/tax/*`. 17 tests nuevos (60 total).
- 2026-09-28: **Fase 3 completa.** Clasificación PUC (Haiku + reglas), deducibilidad E.T., parser CSV, motor conciliación. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS.
- 2026-09-28: **Fase 1 completa.** Schema SQL, seed real, calendario DIAN 2026, PUC, usuarios demo.
- 2026-09-26: Fase 0 completa — scaffold monorepo.
