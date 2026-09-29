# Fase 4 — Cálculo fiscal

Cerrada 2026-09-28.

## Qué se construyó

Módulo puro `backend/app/tax/` que a partir de las facturas ya extraídas y clasificadas produce las obligaciones fiscales del año, cruzándolas con el calendario DIAN 2026 ya cargado.

### Estructura

- `tax/_money.py` — helpers `D()`, `money()`, `ZERO`.
- `tax/uvt.py` — UVT por año (2025: 47.065, 2026: 49.799); conversión COP↔UVT.
- `tax/calendar.py` — ya existía, sin cambios; expone `iva_periods`, `rete_fuente_periods`, `simple_periods`, `ica_bogota_periods` y `due_date_for_digit` (interpolación por último dígito NIT).
- `tax/iva.py` — `compute_iva(invoices)`: generado − descontable (solo `is_deductible=True`) − rete_iva a favor; sin negativos, saldo a favor guardado en snapshot.
- `tax/rete_fuente.py` — `compute_rete_fuente`: suma de retenciones practicadas por concepto (mapa PUC 4-dígitos → concepto DIAN).
- `tax/rete_ica.py` — tarifas ICA Bogotá por mil (por prefijo CIIU 3 dígitos, default 6.9‰). `compute_ica_bogota` (ingresos × tarifa − rete_ica a favor, sin negativos) y `compute_rete_ica` (retenciones ICA practicadas).
- `tax/simple.py` — mapa CIIU (2 dígitos) → grupo Simple; tabla de tarifas bimestrales por grupo y rango de UVT anuales; `compute_simple_bimestral` anualiza (×6) para elegir tramo tarifario.
- `tax/obligations.py` — orquestador. `generate_all(invoices, client, year)` devuelve `list[PlannedObligation]` según régimen/actividad. `generate_and_persist(db, firm_id, client_id, year, period_label?)` hace UPSERT en `tax_obligations` con `on_conflict=(client_id,kind,period_label)`.
- `tax/routes.py` — endpoints staff:
  - `POST /tax/generate/{client_id}?year=2026` — recalcula todo el año.
  - `GET  /tax/calculate/{client_id}/{period_label}` — recalcula solo ese label y devuelve las obligaciones (varias si un mismo label aparece en varios `kind`).
  - `GET  /tax/obligations/{client_id}?year=2026` — lista lo persistido.

### Aplicabilidad por cliente (obligaciones generadas)

| Régimen \ Config | IVA | Rete fuente | ICA Bogotá | Simple |
|---|---|---|---|---|
| ordinario + `iva_frequency` | ✅ | si `is_agente_retencion` | si ciudad = Bogotá | — |
| simple | — | si `is_agente_retencion` | si ciudad = Bogotá | ✅ |

## Reglas fiscales aplicadas (versión simplificada)

- **IVA**: `iva_generado − iva_descontable − rete_iva_favor`. Descontable = solo facturas recibidas con `is_deductible=True` (Fase 3 ya lo evaluó). Saldo negativo → `amount=0`, saldo a favor en snapshot.
- **Rete fuente mensual**: suma directa de `invoices.rete_fuente` en recibidas del mes (la retención ya se calculó al emitir/recibir la factura; aquí solo se totaliza para el Form 350). Agrupado por concepto vía prefijo PUC.
- **ICA Bogotá bimestral**: ingresos (`subtotal` de emitidas) × tarifa por mil según CIIU (prefijo 3), − rete_ica a favor. Sin negativos.
- **Rete ICA**: suma de `rete_ica` en recibidas del bimestre (para agentes retenedores). Se añade al snapshot de la obligación ICA como `rete_ica_practicada`.
- **Simple bimestral**: `ingresos_bimestre × tarifa(grupo, ingresos_anualizados_en_UVT)`. Grupo por CIIU 2 dígitos; tramos por UVT (art. 908 E.T. mod. Ley 2277/2022).

Todas las reglas son honestas para la demo pero **no reemplazan una revisión profesional**. Las tablas de tarifas y CIIU→grupo cubren los códigos del seed y los más frecuentes.

## Idempotencia

`tax_obligations` tiene `unique (client_id, kind, period_label)`. `generate_and_persist` hace `upsert(on_conflict="client_id,kind,period_label")`, por lo que correrlo dos veces no duplica.

## Smoke real (Supabase)

```
Consultora Andina (Simple, CIIU 749):
  6 simple_bimestral + 6 ica_bogota → 12 obligaciones. Suma ~2.6M COP anuales.

Comercializadora Pacífico (Ordinario, CIIU 466, agente retención):
  6 iva_bimestral + 12 rete_fuente + 6 ica_bogota → 24 obligaciones. Suma ~17.8M COP anuales.
```

Rows quedaron en Supabase — son datos demo válidos que Fase 5/6 consumirán.

## Tests (17 nuevos, total repo: 60)

- IVA: generado−descontable, rete_iva a favor, saldo a favor no negativo.
- Rete fuente: `concepto_from_puc`, suma agrupada por concepto.
- ICA: tarifas conocidas y default, cálculo con rete a favor, sin negativos, rete practicada solo recibidas.
- Simple: `grupo_from_ciiu`, `tarifa_simple` por tramo, `compute_simple_bimestral` extremo a extremo.
- Generador: cobertura por régimen, unicidad `(kind, period_label)`, amount cero sin facturas, `due_date` dentro del rango DIAN publicado con interpolación por dígito NIT.

## Deuda / decisiones pendientes

- **Rete IVA practicada**: solo se contabiliza `rete_iva` en emitidas (a favor); no se genera obligación separada de "rete_iva declarar" porque en el seed las recibidas no traen `rete_iva>0`. Cuando aparezca ese caso, agregar `rete_iva` como `kind` propio dentro del generador (o consolidarlo en `rete_fuente` como columna del Form 350; en la práctica DIAN lo declara junto).
- **Renta PJ / grandes contribuyentes**: el calendario tiene las cuotas cableadas pero el generador aún no las calcula (se calcularán en Fase 6 cuando existan reportes anuales y liquidación privada).
- **Régimen Simple anual**: idem — anticipos sí, declaración anual queda para cierre de ejercicio.
- **ICA fuera de Bogotá**: solo cubierto Bogotá; otras ciudades (Medellín, Cali) usarán la misma estructura pero con sus resoluciones.
- **Cálculo Simple**: la anualización ×6 es correcta para el 4º bimestre en adelante pero puede sobrevalorar el tramo tarifario si los primeros bimestres son estacionalmente altos. Aceptable para demo.

## Comandos útiles

```bash
cd backend && source .venv/bin/activate

# Tests
python -m pytest tests/test_tax.py -v

# Recalcular obligaciones de un cliente para todo 2026
curl -X POST -H "Authorization: Bearer $JWT" \
  "$API/tax/generate/$CLIENT_ID?year=2026"

# Consultar una obligación específica
curl -H "Authorization: Bearer $JWT" \
  "$API/tax/calculate/$CLIENT_ID/jul-ago-2026"

# Listar todo lo persistido
curl -H "Authorization: Bearer $JWT" \
  "$API/tax/obligations/$CLIENT_ID?year=2026"
```
