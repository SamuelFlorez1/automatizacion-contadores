# Decisiones — log de arquitectura y producto

Registra decisiones no obvias que afectan al resto del proyecto. Formato ADR-lite. Nuevas entradas al final.

Formato:
```
## YYYY-MM-DD — <título corto>
**Contexto**: qué problema o pregunta motivó la decisión.
**Decisión**: qué se decidió.
**Alternativas consideradas**: qué se descartó y por qué.
**Consecuencias**: qué implica esto para el resto del sistema.
```

---

## 2026-09-26 — Monorepo con backend Python + frontend Next
**Contexto**: separar o unir backend y frontend.
**Decisión**: monorepo. Un solo `git init`, `backend/` y `frontend/` como hermanos.
**Alternativas**: dos repos separados.
**Consecuencias**: más simple para demo y para clonar. Deploys independientes (Railway + Vercel) siguen funcionando.

## 2026-09-26 — Supabase en `sa-east-1` (São Paulo)
**Contexto**: latencia desde Colombia.
**Decisión**: región São Paulo.
**Alternativas**: us-east-1 (más barato/rápido en algunos casos, pero peor latencia CO).
**Consecuencias**: latencia baja aceptable, precio estándar.

## 2026-09-26 — Deploy backend en Railway, frontend en Vercel
**Contexto**: elegir entre Railway y VPS Hostinger existente.
**Decisión**: Railway para backend, Vercel para frontend.
**Alternativas**: VPS Hostinger (más control, menos operación cómoda para demo).
**Consecuencias**: CI y logs limpios; costo predecible; fácil escalar la demo.

## 2026-09-26 — Auth con Supabase desde Fase 1
**Contexto**: el usuario quiere que la demo se vea como producción.
**Decisión**: activar Supabase Auth con roles (`firm_admin`, `accountant`, `client`) desde el arranque, no como fase posterior.
**Consecuencias**: RLS en todas las tablas desde el día 1; middleware en FastAPI para validar JWT.

## 2026-09-26 — Sistema de contexto local basado en archivos
**Contexto**: hacer el proyecto en una sola sesión de Claude quema tokens.
**Decisión**: `CLAUDE.md` + `PLAN.md` + `STATE.md` + `DECISIONS.md` + `docs/phases/phase-N.md` para que cada sesión nueva agarre contexto rápido.
**Consecuencias**: cada fase debe cerrar actualizando estos archivos. Es parte de la "definición de terminado".

## 2026-09-26 — 2 clientes seed (Simple + Ordinario con USD)
**Contexto**: cuánta data sintética generar.
**Decisión**: 2 clientes, uno régimen Simple pequeño, uno Ordinario con importaciones USD; 20–30 facturas cada uno; 3 meses.
**Consecuencias**: cubre los dos regímenes principales y el caso multi-moneda sin inflar el seed.

## 2026-09-26 — XMLs UBL sintéticos (no reales)
**Contexto**: no tenemos XMLs DIAN reales anonimizados.
**Decisión**: generar sintéticos válidos siguiendo UBL 2.1.
**Consecuencias**: 1–2 días extra en Fase 1 para construir el generador correcto. Ventaja: control total sobre casos borde.

## 2026-09-28 — JWT de Supabase validado con JWKS (ES256), no con el secreto HS256
**Contexto**: el proyecto Supabase firma los access tokens con ES256 (signing keys nuevas); `SUPABASE_JWT_SECRET` (HS256) ya no valida.
**Decisión**: `app/auth.py` valida contra `/auth/v1/.well-known/jwks.json` (cacheado, se refresca si aparece un `kid` nuevo) y mantiene fallback HS256 por si se usa un proyecto con secreto legado.
**Consecuencias**: el backend hace una llamada HTTP a Supabase al arrancar el primer request autenticado; no depende de `SUPABASE_JWT_SECRET`.

## 2026-09-28 — Ingesta: originales en Supabase Storage y dedupe por contenido
**Contexto**: los tres canales (upload, WhatsApp, email) deben ser idempotentes y no perder archivos.
**Decisión**: todos pasan por `ingest/service.py`: `dedupe_key = sha256(contenido)` único por despacho (el mismo archivo por otro canal es duplicado); el original se sube al bucket privado `documents` (`{firm}/{client}/{sha}/{nombre}`) antes de extraer. Factura duplicada por negocio (emisor+número+dirección, o CUFE) deja el documento en `ignored`. El cliente `client` siempre sube a su propio `client_id`.
**Alternativas**: dedupe por `messageId` de WhatsApp (no cubre reenvíos ni otros canales).
**Consecuencias**: `channel_ref` guarda el messageId solo como trazabilidad. Extractos CSV se guardan con status `received`; el parseo es Fase 3.

## 2026-09-28 — Advertencias vs. errores en extracción
**Decisión**: solo la falta de datos estructurales (número, fecha, NIT, totales, líneas) es error (`status='error'`). Descuadres de totales, DV de NIT inválido, CUFE sintético y todo lo extraído por Vision quedan como advertencias en `invoices.notes` para revisión del contador.
