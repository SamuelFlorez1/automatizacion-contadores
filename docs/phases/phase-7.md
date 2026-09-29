# Fase 7 — Frontend Next.js

**Cerrada**: 2026-09-28

## Qué se construyó

Dashboard Next 15 (App Router) que recorre toda la demo desde el navegador.

- **Auth Supabase SSR** con `@supabase/ssr` (cookies) — `lib/supabase/{client,server,middleware}.ts`.
- **`middleware.ts`** de Next: refresca cookies con `supabase.auth.getUser()` y redirige a `/login` cualquier ruta que no sea pública; si ya hay sesión y va a `/login`, manda a `/clients`.
- **`app/login`** — email+password contra Supabase Auth (`signInWithPassword`). `useSearchParams` envuelto en `<Suspense>` (Next 15 lo exige en build).
- **Layout despacho** en `app/(app)/layout.tsx` — grid sidebar+topbar, muestra `full_name` + rol desde la tabla `users`, botón cerrar sesión (client component `_components/sign-out.tsx`).
- **`/clients`** — server component, lee `clients` directo por Supabase (RLS filtra por `firm_id`).
- **`/clients/[id]`** con sub-layout que expone tabs (Resumen, Conciliación, Reportes, Cargar):
  - **Resumen**: últimas 20 facturas, 15 movimientos bancarios y todas las obligaciones. 3 tarjetas.
  - **Conciliación**: matches recientes + pendientes de revisión, botón "Correr conciliación" que llama `POST /bank/reconcile/{cid}` con JWT y hace `router.refresh()`.
  - **Reportes**: botones que descargan los PDFs de Fase 6 (mensual y Formulario 300) usando `downloadPdf()` que hace `fetch` con `Authorization: Bearer <access_token>` y dispara descarga vía `Blob`.
  - **Cargar**: 2 formularios — documento (XML/PDF/imagen) contra `POST /ingest/upload`; extracto bancario CSV contra `POST /bank/upload`. `FormData` con JWT.

- **`lib/api.ts`**: helper que saca el `access_token` de la sesión Supabase y adjunta `Authorization: Bearer`. Soporta JSON, `FormData` y descargas PDF (`downloadPdf`).
- **`lib/utils.ts`**: `cn()`, `formatCOP()` (Intl `es-CO`), `formatDate()` (America/Bogota).

## Gotchas

1. **Rutas del backend**: el upload de documentos es `POST /ingest/upload` (no `/upload`) y `POST /bank/upload` **no** acepta `bank_account_id` — lo infiere del CSV. Ambos corregidos.
2. **RLS + JWT del front**: el cliente browser Supabase usa el `access_token` del usuario, así que las consultas del dashboard respetan RLS sin necesidad de service role. El backend sí valida el mismo JWT (vía JWKS, ver DECISIONS 2026-09-28) para las mutaciones.
3. **`useSearchParams` en `/login`**: Next 15 requiere Suspense boundary en producción (`missing-suspense-with-csr-bailout`). El componente `LoginForm` va dentro de `<Suspense>`.
4. **Next 15 dynamic params**: en App Router 15 `params` es `Promise<{id: string}>`; hay que `await` en server components o `use(params)` en client components.
5. **CORS**: el backend está con `allow_origins=["*"]` en `development`. Para Fase 8 (Vercel + Railway) hay que cambiar a lista blanca del dominio Vercel.
6. **Reports 401**: los endpoints `/reports/*` usan `get_current_user` — sin JWT devuelven 401. El front siempre pasa Bearer.
7. **Descarga PDF**: se hace via `Blob` + `<a download>` porque no se puede setear header `Authorization` en un `window.open`. Alternativa futura: signed URLs firmadas server-side.

## Comandos útiles

```bash
cd frontend
pnpm install
pnpm dev                                  # http://localhost:3000
pnpm typecheck
pnpm build

# Variables mínimas (ya en .env.example):
#   NEXT_PUBLIC_SUPABASE_URL
#   NEXT_PUBLIC_SUPABASE_ANON_KEY
#   NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Deuda técnica dejada

- **No hay tests**: por convención del proyecto (solo tests en parser XML, tax, conciliación). Fase 8 podría meter un smoke Playwright si se quiere.
- **Estados de carga son básicos**: sin skeletons; suficiente para demo.
- **Upload manual no muestra progreso**: solo "Subiendo…". Aceptable con archivos pequeños del seed.
- **Sidebar no marca la ruta activa**: cosmético; se puede añadir `usePathname()`.
- **CORS whitelist**: hay que ajustar antes del deploy (Fase 8).
- **Rol `client`** ve la misma UI que staff (con RLS distinta). Fase 8 puede diferenciar la barra lateral.
- **Falta chat del agente en la UI**: el endpoint `/agent/message` existe; una vista de "conversación con IA" quedaría lindo para la demo pero no es bloqueante.
- **Descarga PDF con `Blob`** carga todo el archivo a memoria del browser antes de mostrar el diálogo de guardar. Para PDFs de decenas de MB habría que pasar a signed URLs.

## Verificación

- `pnpm typecheck` limpio.
- `pnpm build` genera 8 rutas (`/`, `/login`, `/clients`, `/clients/[id]`, `/clients/[id]/{reconciliation,reports,upload}`, middleware 91 kB).
- Con credenciales Supabase reales: login → `/clients` → detalle → conciliación (botón OK) → reporte (descarga PDF) → cargar (formulario).
