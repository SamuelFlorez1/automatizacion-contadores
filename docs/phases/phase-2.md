# Fase 2 — Extracción

**Cerrada**: 2026-09-28

## Qué se construyó

- `app/extraction/validators.py`: `nit_dv`, `validate_nit`, `normalize_nit`, `cufe_kind` (official sha384 / seed sha256 / invalid), `dedupe_key` (sha256 del contenido). `seeds/generators.py` los reexporta.
- `app/extraction/xml_ubl.py`: `parse_ubl_invoice(bytes) -> ExtractedInvoice`. Parser lxml sin resolución de entidades (XXE). Errores (`ExtractionError`) solo por datos estructurales faltantes; descuadres de totales / DV de NIT / CUFE van a `warnings`. Lee `PaymentExchangeRate` (USD) y `WithholdingTaxTotal` (05 ReteIVA, 06 ReteFuente, 07 ReteICA).
- `app/extraction/vision.py`: Claude Sonnet (`model_sonnet`) con tool-use forzado `registrar_factura`; acepta PNG/JPG/WEBP/GIF y PDF. Valida DV, descarta CUFE truncado y marca siempre "Extraído con IA".
- `app/ingest/service.py`: pipeline común (dedupe → rate limit → Storage → `documents` → extraer → `invoices`/`invoice_lines`). Deriva `direction` comparando el NIT del cliente con emisor/adquirente.
- Canales: `POST /ingest/upload` (JWT), `POST /webhooks/evolution` (HMAC `x-signature`), `POST /ingest/email` (header `x-ingest-secret`, para n8n).
- `app/auth.py`: JWT Supabase vía JWKS (ES256) → `CurrentUser(id, firm_id, role, client_id)`.
- Rate limit: `INGEST_MAX_DOCS_PER_CLIENT_DAY` (50), día calendario en `America/Bogota`. Tamaño máx: `INGEST_MAX_FILE_BYTES` (10 MB).
- Tests (`tests/test_extraction.py`, 19 en total): NIT, CUFE, dedupe, parser (roundtrip, USD+FX, retenciones, descuadres, campos faltantes, XXE).

## Verificado end-to-end contra Supabase remoto

Upload XML (parsed) → reenvío (duplicate) → XML roto (error con detalle) → .txt (ignored) → PNG vía Vision (extrajo bien; factura ya existía → ignored) → sin token (401) → cliente forzado a su propio `client_id` → WhatsApp con firma mala (401) / buena (parsed) / repetido (duplicate) → email con secreto → rate limit. Datos de prueba borrados después.

## Cambios en el seed / bugs corregidos

- **Bug en `nit_dv` (Fase 1)**: con residuo 1 devolvía 0; el correcto es 1. Corregido y seed re-ejecutado (los XMLs de algunos proveedores tenían DV mal).
- El generador UBL ahora emite `PaymentExchangeRate` (USD) y `WithholdingTaxTotal`; antes el XML no traía FX ni retenciones.

## Comandos útiles

```bash
cd backend && source .venv/bin/activate
python -m pytest -q
uvicorn app.main:app --reload
# firmar un webhook de prueba
python -c "import hmac,hashlib,sys;print(hmac.new(b'SECRET',open('body.json','rb').read(),hashlib.sha256).hexdigest())"
```

Evolution: configurar webhook con evento `MESSAGES_UPSERT`, `webhook_base64: true` y header `x-signature` = HMAC-SHA256 hex del body con `EVOLUTION_WEBHOOK_SECRET`. (Si Evolution no firma nativamente, la firma la pone n8n/proxy — verificar en Fase 5.)

## Gotchas

- `SUPABASE_JWT_SECRET` no sirve: tokens son ES256 (ver DECISIONS).
- `service_role` bypasa RLS: los endpoints filtran por `firm_id`/`client_id` en código.
- Los endpoints son `def` (sync) porque supabase-py es síncrono; FastAPI los corre en threadpool.
- Cliente WhatsApp se identifica por últimos 10 dígitos de `clients.phone`; email por `clients.email`.

## Deuda técnica

- `documents.storage_path` de los documentos del seed sigue apuntando a rutas locales; los nuevos usan Storage.
- Sin reintentos automáticos de documentos en `error`; sin endpoint para reprocesar.
- PDFs: se envían enteros a Claude (sin `pdfplumber` previo); optimizable con texto embebido si el volumen crece.
- Payload real de Evolution y su mecanismo de firma sin probar contra la instancia real (pendiente Fase 5).
- Ingesta no es transaccional (invoice + líneas): si fallan las líneas se borra la factura manualmente.
- Extractos bancarios CSV quedan `received` hasta Fase 3.
