# Fase 1 — Modelo de datos + seed

**Cerrada**: 2026-09-28

## Qué se construyó

### Schema (`backend/migrations/0001_init.sql`)

13 tablas multi-tenant por `firm_id` con RLS activa desde el día 1:

- `firms`, `users` (perfil ligado a `auth.users`), `clients`
- `documents` (raw entrante con `dedupe_key` para idempotencia)
- `invoices` + `invoice_lines` (soporta COP y USD con `fx_rate_to_cop`)
- `bank_accounts` + `bank_transactions` + `reconciliation_matches`
- `tax_obligations` (con `calculation_snapshot` jsonb para auditoría)
- `conversations` + `messages` (agente WhatsApp Fase 5)
- `audit_log`

Funciones helper para RLS: `auth_firm_id()`, `auth_role()`, `auth_client_id()`. Policies aplicadas a todas las tablas: staff (`firm_admin`, `accountant`) ve todo su firm; `client` ve solo sus propios datos.

### Calendario DIAN 2026 (`backend/app/tax/calendar_2026.json`)

Cubre: IVA bimestral (6 periodos), IVA cuatrimestral (3 periodos), Retención en la fuente (12 meses), Renta PJ ordinaria (2 cuotas), Renta grandes contribuyentes (3 cuotas), Régimen Simple (6 anticipos + declaración anual), ICA Bogotá bimestral.

Los rangos vienen de fuentes públicas (DIAN, Actualícese, El Tiempo, Bogotá SDH). El día exacto por último dígito NIT se calcula con `tax/calendar.py:due_date_for_digit` interpolando dentro del rango publicado (patrón canónico DIAN cuando el decreto no publica día explícito por dígito).

### PUC resumido (`backend/app/tax/puc.json`)

~100 cuentas del Decreto 2650/1993 con `applies_to: [servicios, comercio]`. Cubre lo suficiente para clasificar facturas de servicios y comercio en Fase 3. Cargar PUC completo cuando se necesite.

### Seed (`backend/seeds/seed.py` + `generators.py`)

**Datos**: 1 firm + 2 clientes (Simple servicios, Ordinario comercio con USD) + 53 facturas en jul–sep 2026 + 3 cuentas bancarias + 56 mov bancarios + 61 documentos (53 XML + 8 imágenes PNG).

**Generadores**:
- `nit_dv()`: dígito de verificación con pesos oficiales DIAN
- `build_ubl_xml()`: UBL 2.1 con estructura DIAN (subset válido para demo; no incluye extensiones firma, se puede añadir en producción)
- `synthetic_cufe()`: sha256 truncado marcado como sintético
- `render_invoice_png()`: PIL, factura simple para pruebas de Claude Vision
- `write_bank_csv()`: normalizado con dedupe_key

**Coherencia bancaria**: facturas con `payment_status='paid'` generan tx bancaria correspondiente ±3-25 días; se agregan 5 retiros ATM huérfanos por cuenta para que la conciliación de Fase 3 tenga trabajo real (no todo hace match).

### Auth (`backend/seeds/seed_users.py`)

4 usuarios demo creados en `auth.users` vía `supabase.auth.admin` y enlazados en `public.users` con `role` + `firm_id` + `client_id`.

## Comandos útiles

```bash
cd backend
source .venv/bin/activate

# Aplicar / re-aplicar migración
python -c "import psycopg, pathlib; \
    url=[l.split('=',1)[1].strip() for l in pathlib.Path('../.env').read_text().splitlines() if l.startswith('SUPABASE_DB_URL=')][0]; \
    psycopg.connect(url, sslmode='require').cursor().execute(pathlib.Path('migrations/0001_init.sql').read_text())"

# Repoblar seed (borra y vuelve a insertar)
python -m seeds.seed

# Recrear usuarios (idempotente)
python -m seeds.seed_users
```

## Decisiones locales

- **Postgres directo con psycopg** en vez del SDK supabase-py para las migraciones y el seed: el SDK no expone `execute raw SQL` cómodo, y psycopg permite transacciones limpias con `DELETE` en cascada.
- **`SUPABASE_DB_URL` en `.env` gitignored**: contiene la contraseña del rol `postgres`. Nunca imprimirla en logs.
- **Interpolación por dígito NIT**: no encontré una fuente pública con la tabla explícita por dígito, así que se documenta la convención en el JSON. Si el usuario consigue el decreto oficial 2025 de plazos DIAN 2026 (PDF), se puede reemplazar por fechas exactas.
- **ICA Bogotá bimestres 4-6**: extrapolados a partir del patrón; marcados `"source": "estimated"` en el JSON para revisar cuando salgan las fechas oficiales.
- **PDFs**: no se generaron por ahora (WeasyPrint necesita libs nativas del sistema). Se sustituyeron por PNG con Pillow, suficientes para probar Vision. Si Fase 2 pide PDFs reales, se agrega reportlab o `weasyprint` con Docker.
- **CUFE sintético**: sha256 truncado, NO es el algoritmo oficial de la DIAN. El validador de Fase 2 lo detectará como "seed" y no lo rechazará.
- **Passwords demo**: hardcoded en `seed_users.py` — se cambian antes de exponer la demo públicamente.

## Gotchas

- `create_client` de supabase-py 2.x tira warning con URLs http; usar https siempre.
- Si `python -m seeds.seed` da `FATAL: too many connections`, esperar unos segundos y reintentar (Supabase free tiene ~60 conns).
- El seed **borra todos los datos** de las tablas del dominio (excepto `auth.users`) al arrancar. Es intencional: seed es reproducible.
- Las policies RLS **no aplican al `service_role`** (bypassa por defecto en Supabase). Cualquier query desde el backend con service_role ve todo — es el patrón esperado para trabajos backend, pero al construir endpoints Fase 2+ hay que filtrar por `client_id` en la app o usar el JWT del usuario.

## Deuda dejada

- `nit_dv` está en `seeds/generators.py`; Fase 2 lo debería mover a `app/extraction/validators.py` y reexportar desde seeds.
- No hay CUFE oficial (algoritmo DIAN real requiere firmar con certificado). Ok para demo.
- `documents.storage_path` apunta a rutas locales del repo (`backend/seeds/invoices_xml/…`). Cuando Fase 2 empiece con Storage real de Supabase, migrar a URLs firmadas.
- Tests de módulos críticos (parser XML, cálculos fiscales, motor conciliación) no existen todavía — Fases 2/3/4 los agregan.
- `image_path` se pasa a `render_invoice_png` con ~15% cobertura arbitraria. Si se necesitan más imágenes para entrenar prompts de Vision, ajustar el módulo del `if i % 7 == 0`.

## Smoke test

1. `cd backend && source .venv/bin/activate`
2. `python -m seeds.seed` → debe imprimir counts y `✅ Seed listo.`
3. `python -m seeds.seed_users` → debe imprimir 4 emails con sus roles
4. Login en Supabase Dashboard → Authentication → Users: ver los 4 usuarios
5. Table Editor → `invoices` filtrado por firm: 53 filas
6. `ls backend/seeds/invoices_xml/ | wc -l` → 53
7. `ls backend/seeds/invoices_images/` → 8 PNGs
8. `ls backend/seeds/bank_statements/` → 3 CSVs
