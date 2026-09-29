# Fase 3 — Clasificación PUC + Conciliación bancaria

**Cerrada**: 2026-09-28

## Qué se construyó

### Clasificación PUC (`app/classification/`)
- `puc.py`:
  - `classify_invoice(invoice, trade, force_rules=False)` → `Classification(puc_account, confidence, rationale, source)`.
  - **Haiku 4.5** con tool-use forzado `sugerir_cuenta`; el prompt entrega solo el subset del catálogo aplicable a la actividad (`servicios` / `comercio`) y a la dirección (`recibida` → 5xxx/6xxx, `emitida` → 41xx).
  - Valida que el código devuelto exista en el catálogo; si no, cae a reglas.
  - `_rule_based`: 21 reglas por regex (arriendo→512010, ETB/Codensa/agua/gas→513xxx, honorarios→511xxx, mantenimiento, seguros, viajes, mercancía, etc.). Fallback: `5195` (diversos).
  - `classify_and_persist(db, invoice_id)` clasifica, evalúa deducibilidad y escribe `invoices.puc_account`, `classification_confidence`, `is_deductible`, y agrega notas.
- `deductibility.py`: reglas simplificadas (E.T. 107, 771-2, 771-5).
  - Solo cuentas 5xxx/6xxx son deducibles.
  - Requiere NIT del proveedor y número de factura.
  - Emitidas → `is_deductible=None` (son ingresos, no aplica).
  - Marca advertencia si el total ≥ 100 UVT (bancarización).

### Conciliación bancaria (`app/reconciliation/`)
- `csv_parser.py`: parser robusto de extractos CSV.
  - Comentarios `#` metadata → hint de cuenta bancaria (banco, número enmascarado, moneda).
  - Encabezados en español/inglés, separadores `, ; | \t`, encodings UTF-8/latin-1.
  - Formatos numéricos europeo (`1.234.567,89`) y anglosajón; paréntesis contables.
  - `dedupe_key` = sha256(`account|date|amount|ref|desc`).
  - Ignora filas de saldo inicial/final.
- `engine.py`: motor puro, testeable sin DB.
  - Estrategias en orden: **transfer_internal** → **exact por referencia** (invoice_number o CUFE en la referencia bancaria, tolera diferencia de hasta 25 % por retenciones) → **exact por monto+proveedor único** (ventana ±45 días) → **fuzzy** (monto ±2 %, similitud de nombre ≥ 0.7, ±10 días).
  - Ambigüedad multi-candidato: ranking por similitud, desempate por fecha.
  - Confianza por match: exacto 1.0 → 0.92 (retenciones) → 0.7 (multi-candidato) → 0.6–0.9 (fuzzy).
  - Una factura solo se consume una vez; ATM sin referencia queda `unmatched`.
- `service.py`: pega el motor con Supabase.
  - `ingest_bank_csv()`: parsea → crea/reusa `bank_accounts` → inserta `bank_transactions` idempotente por `(firm_id, dedupe_key)` → dispara reconciliación completa del cliente.
  - `reconcile_client()`: reejecuta matching sobre `bank_transactions` `unmatched` del cliente.
  - Facturas con match exacto → `payment_status='paid'`.
- `routes.py`:
  - `POST /bank/upload` (staff) — multipart `file` + `client_id`.
  - `POST /bank/reconcile/{client_id}` — re-corre matching.
  - `POST /invoices/{id}/classify` — clasifica una factura (?force_rules=true evita Anthropic).
  - `POST /clients/{cid}/classify` — batch sobre facturas sin `puc_account`.

## Verificado end-to-end contra Supabase remoto

- **Consultora Andina** (Bancolombia COP, 19 movimientos): 14 exactos, 5 unmatched (todos retiros ATM). Reejecución de reconcile: idempotente (no vuelve a marcar).
- **Comercializadora Pacífico** (Davivienda COP + Bancolombia USD, 34 movimientos): 2 exactos por referencia; el resto queda unmatched porque el generador del seed usó referencias `FCB-R-YYYYMM-###` que no siempre coinciden con el `invoice_number`, además de facturas recurrentes por el mismo monto (ambigüedad real). Deuda técnica documentada abajo.
- **Clasificación por reglas** sobre 3 facturas recibidas: mapea correctamente arriendo → 512010, energía → 513530, telefonía → 513535.
- Todos los datos insertados por el smoke se limpiaron (`reconciliation_matches`, `bank_transactions`, `bank_accounts` y reversión de `payment_status`).

## Tests

`tests/test_reconciliation.py` (14) + `tests/test_classification.py` (10). Total del repo: **43 pasan** (`pytest -q`).

Cubren:
- Parser CSV: seeds reales COP y USD, formatos numéricos, columnas faltantes.
- Motor: exact por referencia (con y sin retenciones), monto+proveedor único, ambigüedad, fuzzy, ATM ignorado, traslados internos, factura no reutilizada, prioridad por similitud > fecha.
- Clasificación por reglas: arriendo, telefonía, ingreso servicios/comercio, fallback diversos.
- Deducibilidad: sin NIT, solo gastos/costos, ingreso emitido, umbral bancarización.

## Endpoints activos (OpenAPI)

```
POST /bank/upload
POST /bank/reconcile/{client_id}
POST /invoices/{invoice_id}/classify
POST /clients/{client_id}/classify
POST /ingest/upload · /ingest/email · /webhooks/evolution
GET  /health · /
```

## Comandos útiles

```bash
cd backend && source .venv/bin/activate
python -m pytest -q
# Subir un CSV del seed contra Supabase (script inline):
python -c "
from app.db.client import get_service_client
from app.reconciliation.service import ingest_bank_csv
from pathlib import Path
db = get_service_client()
c = db.table('clients').select('id, firm_id').ilike('legal_name', '%Andina%').execute().data[0]
r = ingest_bank_csv(db, firm_id=c['firm_id'], client_id=c['id'],
                    content=Path('seeds/bank_statements/consultora_andina_bancolombia_2026Q3.csv').read_bytes(),
                    filename='andina.csv')
print(r.summary.as_dict())
"
```

## Gotchas

- El pago bancario típicamente descuenta retenciones (rete-fuente/IVA/ICA) del total facturado. El motor lo maneja: si la referencia coincide con `invoice_number`, tolera hasta 25 % de diferencia y baja la confianza a 0.92.
- `_load_client_transactions(only_unmatched=True)` no toca lo ya emparejado → `reconcile_client` es idempotente y puede correrse a demanda cuando llegan facturas nuevas.
- Cuando dos facturas recurrentes del mismo proveedor tienen el mismo monto, el motor elige por proximidad de fecha y baja el `match_type` a `fuzzy` para que el contador confirme.
- Haiku puede devolver un código fuera del catálogo; siempre se valida contra `_accounts_for()` y se cae a reglas si no cuadra. Con `ANTHROPIC_API_KEY` vacía el sistema funciona 100 % offline (ideal para tests y CI).

## Deuda técnica

- **Seed Pacifico**: referencias en CSVs no siempre coinciden con `invoice_number` reales y hay facturas recurrentes con montos idénticos. Regenerar el seed (o el matcher) para que la demo se vea más limpia.
- **Bancarización** (art. 771-5): solo advertimos por monto. Cuando la conciliación cierre el círculo, se podrá inferir el medio de pago (banco vs. efectivo) y aplicar la regla completa.
- **Clasificación batch** es serial (una llamada Haiku por factura). Con volúmenes altos habría que hacerlo por lotes o async.
- **Multi-currency**: extractos USD entran, pero el matcher no convierte a COP en runtime (usa `total_cop` de la factura). Un pago USD contra una factura solo cuadra si `total` (USD) y CSV usan la misma escala. Fase 4 revisará FX.
- **Split payments** (una factura pagada en varios abonos) no soportado: cada match consume la factura entera.
- **Sin UI**: los estados `review`/`unmatched` no se pueden resolver desde el dashboard (Fase 7).
