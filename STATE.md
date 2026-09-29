# Estado actual del proyecto

**Última actualización**: 2026-09-28
**Fase actual**: Fase 1 cerrada ✅ — próxima sesión arranca **Fase 2 (Extracción)**
**Última sesión**: Fase 1 completa — schema aplicado a Supabase, seed corriendo, auth con roles y calendario/PUC cableados.

---

## ¿En qué vamos?

**Fase 1 cerrada.** Ver `docs/phases/phase-1.md` para bitácora completa.

**Base de datos remoto** (`flwxzcqggtefhxnxxfhy` en `sa-east-1`):
- 13 tablas creadas con RLS por `firm_id`
- 1 despacho, 2 clientes (Simple servicios / Ordinario comercio con USD)
- 53 facturas, 62 líneas, 3 cuentas bancarias, 56 movimientos, 61 documentos
- 4 usuarios demo (firm_admin, accountant, 2 clientes)

**Credenciales en `.env`**:
- ✅ Anthropic, Supabase URL/service_role/anon/JWT
- ✅ `SUPABASE_DB_URL` (postgres directo — usado por migraciones y seed)
- ⏸️ Evolution API / n8n — se piden en Fase 5

## Próximo paso concreto — arrancar Fase 2 (Extracción)

Al abrir sesión nueva:

1. Sanity check rápido:
   - `cd backend && source .venv/bin/activate && python -c "from app.tax.calendar import load_calendar; print(len(load_calendar()['iva_bimestral']['periods']))"`
   - Login en `https://flwxzcqggtefhxnxxfhy.supabase.co` con cualquier usuario demo para verificar Auth.
2. Empezar Fase 2:
   - `backend/app/extraction/xml_ubl.py` — parser DIAN con validación estructural
   - `backend/app/extraction/validators.py` — dígito NIT (ya está en `seeds/generators.py:nit_dv`, moverlo o reexportar), CUFE, hash duplicados
   - `backend/app/extraction/vision.py` — Claude Vision con prompt estructurado
   - `backend/app/ingest/{whatsapp,email,upload}.py` — idempotencia por `dedupe_key`
   - Firma HMAC en webhook Evolution
   - Tests unitarios: parser XML, validador NIT, CUFE
   - Rate limit por cliente/día
3. Cerrar Fase 2 actualizando este archivo, `PLAN.md`, y creando `docs/phases/phase-2.md`.

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

- 2026-09-28: **Fase 1 completa.** Schema SQL aplicado a Supabase remoto; 53 facturas seed; calendario DIAN 2026 + PUC cableados; usuarios demo con roles vía Supabase Auth.
- 2026-09-28: `SUPABASE_DB_URL` cargada; migraciones se ejecutan directo con psycopg.
- 2026-09-26: Fase 0 completa — scaffold monorepo. Ver `docs/phases/phase-0.md`.
