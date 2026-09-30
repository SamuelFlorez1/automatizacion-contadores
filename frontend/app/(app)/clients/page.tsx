import Link from "next/link";
import { MapPin, Users, ArrowUpRight } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { EmptyState } from "@/components/empty-state";
import { RegimenBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

export default async function ClientsPage() {
  const supabase = await createClient();
  const { data: clients, error } = await supabase
    .from("clients")
    .select("id, legal_name, trade_name, nit, tax_regime, ica_city")
    .order("legal_name");

  const list = clients || [];

  // Count of invoices this month per client — a small quality-of-life stat
  const startOfMonth = new Date();
  startOfMonth.setDate(1);
  const { data: invStats } = await supabase
    .from("invoices")
    .select("client_id")
    .gte("issue_date", startOfMonth.toISOString().slice(0, 10));

  const invCount = new Map<string, number>();
  for (const row of invStats || []) {
    invCount.set(row.client_id, (invCount.get(row.client_id) || 0) + 1);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Clientes</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {list.length === 0
              ? "Aún no tienes clientes asignados."
              : `${list.length} ${list.length === 1 ? "empresa activa" : "empresas activas"} en el despacho.`}
          </p>
        </div>
        <Button variant="secondary" disabled title="Próximamente">
          Nuevo cliente
        </Button>
      </div>

      {error && (
        <div className="rounded-[8px] border border-danger/40 bg-danger-soft px-4 py-3 text-sm text-danger-fg">
          No pudimos cargar los clientes: {error.message}. Intenta refrescar la página.
        </div>
      )}

      {list.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Sin clientes visibles"
          description="Pide a un admin que te asigne empresas para verlas aquí."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((c) => {
            const n = invCount.get(c.id) || 0;
            return (
              <Link
                key={c.id}
                href={`/clients/${c.id}`}
                className="group relative flex flex-col justify-between rounded-card border border-line bg-surface-card p-5 shadow-card transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-pop"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-base font-semibold text-ink">{c.legal_name}</p>
                      {c.trade_name && (
                        <p className="mt-0.5 truncate text-xs text-ink-subtle">{c.trade_name}</p>
                      )}
                    </div>
                    <ArrowUpRight className="h-4 w-4 shrink-0 text-ink-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <RegimenBadge regime={c.tax_regime} />
                    {c.ica_city && (
                      <span className="inline-flex items-center gap-1 text-xs text-ink-subtle">
                        <MapPin className="h-3 w-3" />
                        {c.ica_city}
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-5 flex items-center justify-between border-t border-line pt-4 text-xs">
                  <div className="text-ink-subtle">
                    NIT <span className="font-mono tabular-nums text-ink-muted">{c.nit}</span>
                  </div>
                  <div className="text-ink-subtle">
                    <span className="font-mono tabular-nums text-ink">{n}</span> factura{n === 1 ? "" : "s"} este mes
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
