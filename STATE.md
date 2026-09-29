# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 3 cerrada ✅ — próxima sesión arranca **Fase 4 (Cálculo fiscal)**
**Última sesión**: Fase 3 completa — clasificación PUC (Haiku + reglas offline), deducibilidad, parser CSV y motor de conciliación con retenciones toleradas. 43 tests pasan.

---

## ¿En qué vamos?

**Fase 3 cerrada.** Ver `docs/phases/phase-3.md`. Endpoints nuevos: `POST /bank/upload`, `POST /bank/reconcile/{cid}`, `POST /invoices/{id}/classify`, `POST /clients/{cid}/classify`.

Smoke contra Supabase remoto: Andina 14/19 exactos (los 5 restantes son ATMs), Pacifico limitado por ambigüedades del seed (documentadas como deuda). Todo se limpió tras la prueba.

**Credenciales en `.env`**: ✅ Anthropic, Supabase. ⏸️ Evolution / n8n (Fase 5).

## Próximo paso concreto — arrancar Fase 4

1. `backend/app/tax/iva.py`: cálculo bimestral/cuatrimestral desde `invoices` según `clients.iva_frequency`.
2. `tax/rete_fuente.py`, `tax/rete_ica.py`, `tax/simple.py` — cada uno por concepto/ciudad/régimen.
3. Generador de `tax_obligations` combinando facturas + `tax/calendar_2026.json` (ya cargado). Idempotente por `(client_id, kind, period_label)`.
4. Endpoint `GET /tax/calculate/{client_id}/{period}` devuelve obligaciones + snapshot.
5. Tests: cálculos fiscales (IVA con retenciones, Simple por actividad, ICA por ciudad).
6. Cerrar fase con STATE/PLAN/phase-4.md + commit `feat(phase-4)`.

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

- 2026-09-28: **Fase 3 completa.** Clasificación PUC (Haiku + reglas), deducibilidad E.T., parser CSV robusto, motor de conciliación con tolerancia a retenciones y tie-break por similitud+fecha. 43 tests.
- 2026-09-28: **Fase 2 completa.** Parser UBL, Vision, ingesta 3 canales, auth JWKS. Corregido bug de `nit_dv` (residuo 1).
- 2026-09-28: **Fase 1 completa.** Schema SQL aplicado a Supabase remoto; 53 facturas seed; calendario DIAN 2026 + PUC cableados; usuarios demo con roles vía Supabase Auth.
- 2026-09-28: `SUPABASE_DB_URL` cargada; migraciones se ejecutan directo con psycopg.
- 2026-09-26: Fase 0 completa — scaffold monorepo. Ver `docs/phases/phase-0.md`.
