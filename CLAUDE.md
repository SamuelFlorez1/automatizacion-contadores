# Contexto para Claude — Despacho Contable Automatizado

Este archivo se carga automáticamente al inicio de cada sesión de Claude Code en este repo. Léelo completo antes de hacer nada más.

## Qué es este proyecto

Demo vendible de un sistema end-to-end que automatiza la operación de un despacho contable colombiano. WhatsApp + IA + conciliación bancaria + agente conversacional + reportes. Es una **demo pública** que debe verse como producción, pero no es producción real.

**No incluye**: banca real, DIAN real, Meta Business verificado, pagos, KYC.

## Cómo trabajamos aquí

El proyecto se desarrolla **por fases**, una fase = una sesión de Claude Code (para no quemar contexto). Cada fase entrega algo demoable end-to-end.

**Al empezar una sesión nueva, en este orden:**
1. Lee `STATE.md` — te dice en qué fase estamos y el próximo paso concreto.
2. Lee `PLAN.md` — plan completo con checkboxes.
3. Lee `DECISIONS.md` — decisiones tomadas y por qué.
4. Si vas a arrancar una fase nueva, lee la fase anterior en `docs/phases/phase-N.md` para conocer contexto heredado.

**Al terminar una fase (o antes de que el usuario cierre la sesión):**
1. Actualiza `STATE.md` con el estado actual y el próximo paso claro.
2. Marca en `PLAN.md` lo completado con `[x]`.
3. Si se tomaron decisiones no obvias, agrégalas a `DECISIONS.md`.
4. Crea/actualiza `docs/phases/phase-N.md` con: qué se construyó, gotchas, comandos útiles, deuda técnica dejada.
5. Commit con mensaje claro: `feat(phase-N): <resumen>`.

## Reglas del proyecto

- **Idioma**: código en inglés, UI y prompts a Claude en español, commits en inglés.
- **Zona horaria**: `America/Bogota` en todo el stack.
- **Moneda**: COP por defecto, USD soportado para importaciones.
- **Modelos IA**: Sonnet 5 (`claude-sonnet-5`) para extracción compleja y agente; Haiku 4.5 (`claude-haiku-4-5-20251001`) para clasificación en volumen.
- **Idempotencia**: todo webhook debe ser idempotente con `dedupe_key`.
- **Auth**: Supabase Auth con roles `firm_admin`, `accountant`, `client` desde el arranque.
- **Errores**: si extracción falla, documento queda en `status='error'` con detalle; nunca se pierde el archivo original.

## Stack técnico decidido

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11 + FastAPI + Pydantic v2 |
| DB | Supabase (Postgres) en región `sa-east-1` |
| Frontend | Next.js 15 + TypeScript + Tailwind + shadcn/ui |
| IA | Anthropic Claude (Sonnet 5 + Haiku 4.5) |
| Orquestación | n8n self-hosted (Hostinger, ya existe) |
| WhatsApp | Evolution API self-hosted (Hostinger, ya existe) |
| Deploy backend | Railway |
| Deploy frontend | Vercel |
| Parsing | lxml (UBL), pdfplumber, Claude Vision |
| PDFs generados | WeasyPrint |

## Alcance del seed (datos demo)

- 1 despacho
- 2 clientes: uno **Régimen Simple** pequeño, uno **Ordinario** mediano con importaciones USD
- ~20–30 facturas por cliente
- 3 meses de histórico
- XMLs UBL 2.1 **sintéticos** válidos (no tenemos reales)
- CSVs bancarios sintéticos coherentes con las facturas

## Qué NO hacer

- No crear archivos de documentación fuera de este sistema (`CLAUDE.md`, `PLAN.md`, `STATE.md`, `DECISIONS.md`, `docs/phases/*`) salvo que aporten valor claro.
- No refactorizar por adelantado. Fase actual, sin más.
- No agregar tests fuera de los tres módulos críticos: parser XML UBL, cálculos fiscales, motor de conciliación.
- No introducir servicios nuevos (Redis, Celery, etc.) sin discutirlo. Empezamos simple.
