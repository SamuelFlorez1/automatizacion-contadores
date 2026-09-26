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
