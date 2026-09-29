# Fase 6 — Reportes PDF

**Estado**: ✅ cerrada.
**Fecha**: 2026-09-28.
**Tests**: 13 nuevos, 85 en total.

## Qué se construyó

### Módulos nuevos
- `backend/app/reports/monthly.py`
  - Funciones puras: `build_income_statement`, `build_cash_flow`,
    `build_top_expenses`, `build_dataset`.
  - `parse_period("YYYY-MM")` → rango del mes.
  - `fetch_and_build(db, ...)` consulta invoices + bank_transactions +
    tax_obligations del mes y del mes anterior (comparativo).
  - `MonthlyDataset.variation_utilidad` calcula variación % vs mes anterior.
- `backend/app/reports/iva_form300.py`
  - `build_form300(...)`: separa ventas gravadas / excluidas / exportación,
    compras gravadas, y prellena 10 casillas del Formulario 300 (32, 33, 34,
    41, 48, 55, 64, 77, 84, 85). Reusa `compute_iva` de Fase 4.
  - `fetch_and_build(db, ...)` sirve el prellenado para el bimestre pedido y
    cruza con `tax_obligations` para el `due_date`.
- `backend/app/reports/pdf.py`
  - Jinja2 con filtros `cop`, `fmt_date`, `pct`.
  - `render_html(name, ctx)` + `html_to_pdf(html)` (WeasyPrint import diferido).
- `backend/app/reports/narrative.py`
  - `generate_narrative(ds)` — párrafo con Sonnet 5. Fallback determinístico
    si no hay API key o si Anthropic falla.
- `backend/app/reports/routes.py`
  - `GET /reports/monthly/{client_id}/{YYYY-MM}` → application/pdf.
  - `GET /reports/iva/{client_id}/{period_label}` → application/pdf.
  - Ambos aceptan `?format=html` para debug sin invocar WeasyPrint.
  - `?with_narrative=false` desactiva Sonnet.

### Templates
- `backend/app/reports/templates/_base.html` — layout con @page A4, cabecera
  con marca, footer con número de página. Todo inline (WeasyPrint no depende
  de assets externos).
- `monthly.html` — extiende _base. Secciones: narrativa, estado resultados
  (con comparativo mes anterior), impuestos, flujo caja, top 10 gastos,
  obligaciones del mes.
- `iva_form300.html` — resumen, casillas prellenadas, saldo a pagar/favor.

### n8n
- `n8n/flows/monthly-reports.json` — completado. Cron mensual (1º del mes 7am
  America/Bogota), lista clientes en Supabase REST, itera y llama
  `GET /reports/monthly/{id}/{YYYY-MM}` con JWT cron.
  Variables de entorno esperadas: `API_BASE`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `CRON_JWT`.

### Wiring
- `backend/app/main.py` incluye `reports_routes.router`.

## Decisiones importantes

- **Builders puros + persistencia separada**: la lógica vive en funciones que
  reciben listas (`build_income_statement`, `build_form300`, etc.). La capa
  `fetch_and_build` solo arma rangos y consulta Supabase. Esto permite testear
  sin DB y facilita reusar el dataset desde otros disparadores (email, cron).
- **Costos vs. gastos por PUC**: cuentas `6xxx`/`7xxx` cuentan como costo,
  `5xxx` como gasto operacional. La utilidad bruta = ingresos − costos; la
  utilidad operacional = utilidad bruta − gastos.
- **Flujo caja con fallback**: si el mes no tiene extracto bancario cargado,
  se usa el total facturado como estimación (marcado en el PDF con nota
  “Sin extracto bancario cargado”).
- **Narrativa opcional y con fallback**: sin `ANTHROPIC_API_KEY`, sin depender
  de Sonnet, el sistema entrega igual una descripción decente basada en las
  cifras. Con API key, Sonnet 5 escribe 2-4 frases ejecutivas en español.

## Gotchas / deuda técnica

- **WeasyPrint necesita libs de sistema** (`pango`, `cairo`, `gdk-pixbuf`).
  Instaladas en local vía `brew install pango cairo gdk-pixbuf libffi`. En
  Railway (Fase 8) hay que agregar apt packages en `nixpacks.toml` o `Dockerfile`:
  `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi8`.
- **DYLD_LIBRARY_PATH en macOS**: para los tests locales pasamos
  `DYLD_LIBRARY_PATH=/opt/homebrew/lib`. Los dos tests E2E usan
  `pytest.skipif(not _weasy_available)` para no romper CI sin las libs.
- **Renta PJ/GC y Simple anual** siguen sin cálculo. El calendario los tiene,
  pero no hay `compute_renta_*`. Deuda que arrastramos a otra fase.
- **Reportes se generan on-demand** (no se almacenan en Supabase Storage). Si
  el volumen crece, conviene cachearlos o subirlos al bucket.

## Comandos útiles

```bash
# Test suite completa (con lib path de macOS)
DYLD_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q

# Ver el HTML de un mensual sin WeasyPrint (arrancado uvicorn con auth mock/real)
GET /reports/monthly/{client_id}/2026-07?format=html

# Ver el PDF
GET /reports/monthly/{client_id}/2026-07

# IVA
GET /reports/iva/{client_id}/jul-ago-2026?format=html
```

## Siguiente paso

Fase 7 — Frontend Next.js. Login Supabase + páginas cliente/facturas/
conciliación/reportes (link a los endpoints PDF de esta fase).
