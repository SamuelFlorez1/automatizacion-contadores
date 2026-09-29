# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 5 cerrada ✅ — próxima sesión arranca **Fase 6 (Reportes PDF)**
**Última sesión**: Fase 5 completa — agente WhatsApp (5 tools + Sonnet loop), endpoint `/agent/message`, envío Evolution, cron recordatorios, 3 flujos n8n exportados. 72 tests pasan.

---

## ¿En qué vamos?

**Fase 5 cerrada.** Ver `docs/phases/phase-5.md`. Endpoints nuevos:
- `POST /agent/message` — punto de entrada del agente.
- `POST /notifications/reminders/run` — cron (header `x-cron-secret`).
- `POST /notifications/reminders/preview` — vista previa staff (JWT).

Webhook `/webhooks/evolution` ahora también responde a mensajes de texto (los deriva al agente y contesta).

**Credenciales en `.env`**: ✅ Anthropic, Supabase. ⏸️ Evolution (`EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE_NAME`) siguen pendientes. Sin ellas, el envío queda log-only pero el resto del pipeline funciona.

## Próximo paso concreto — arrancar Fase 6

1. `reports/monthly.py` — armar dataset por cliente/período (estado resultados, flujo caja, top gastos, comparativo mes anterior). Reusa lo que Fase 3 clasificó y Fase 4 calculó.
2. Templates HTML en `reports/templates/` + WeasyPrint (`pip install weasyprint` en el venv; falta instalar).
3. `reports/iva_form300.py` — prellena Formato 300 DIAN con datos de `tax_obligations` + facturas.
4. Análisis IA opcional con Sonnet 5: párrafo narrativo al inicio del PDF.
5. Endpoints `GET /reports/monthly/{cid}/{period}` y `/reports/iva/{cid}/{period}` que devuelven `application/pdf`.
6. Rellenar el nodo TODO de `n8n/flows/monthly-reports.json` para generar reportes el 1º del mes.
7. Tests: renderiza sin error, PDF > 0 bytes, campos numéricos coinciden con `tax_obligations`.
8. Cerrar STATE/PLAN/phase-6.md + commit `feat(phase-6)`.

**Preparativo**: instalar WeasyPrint y sus deps de sistema (`brew install pango cairo gdk-pixbuf libffi` en macOS) antes de arrancar.

## Bootstrap de sesión nueva

```bash
cd "/Users/newuser/Automatizacion contadores"
cat CLAUDE.md STATE.md PLAN.md DECISIONS.md
ls docs/phases/
git log --oneline -20
```

## Bloqueos / esperando algo

- **Fase 6**: WeasyPrint no instalado en el venv local + faltan deps de sistema.
- **Evolution**: sin credenciales; envío WhatsApp queda log-only. No bloquea Fase 6.
- **Deuda tax**: Renta PJ/GC y declaración anual Simple aún sin calcular — el calendario ya los tiene, se atacan en Fase 6 junto con los reportes anuales.

## Usuarios demo (Fase 1)

| Rol         | Email                           | Password        |
|-------------|---------------------------------|-----------------|
| firm_admin  | admin@despachodemo.co           | DemoAdmin2026!  |
| accountant  | contador@despachodemo.co        | DemoConta2026!  |
| client      | andina@clientedemo.co           | DemoAndi2026!   |
| client      | pacifico@clientedemo.co         | DemoPaci2026!   |

## Cambios recientes

- 2026-09-28: **Fase 5 completa.** Agente WhatsApp (5 tools + Sonnet loop, `MAX_ITERS=10`), `/agent/message`, envío Evolution, cron `/notifications/reminders/run`, 3 flujos n8n exportados. 12 tests nuevos (72 total).
- 2026-09-28: **Fase 4 completa.** IVA/rete_fuente/rete-ICA/ICA Bogotá/Simple, generador idempotente de `tax_obligations`, endpoints `/tax/*`. 17 tests nuevos (60 total).
- 2026-09-28: **Fase 3 completa.** Clasificación PUC (Haiku + reglas), deducibilidad E.T., parser CSV, motor conciliación. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS.
- 2026-09-28: **Fase 1 completa.** Schema SQL, seed real, calendario DIAN 2026, PUC, usuarios demo.
- 2026-09-26: Fase 0 completa — scaffold monorepo.
