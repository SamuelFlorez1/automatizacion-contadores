import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, FileText, Banknote, FileBarChart2, Upload } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { RegimenBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";
import { ClientTabsClient } from "./_client-tabs";

export default async function ClientLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const { data: client } = await supabase
    .from("clients")
    .select("id, legal_name, trade_name, nit, tax_regime, ica_city")
    .eq("id", id)
    .maybeSingle();

  if (!client) notFound();

  return (
    <div className="mx-auto max-w-7xl">
      <Link
        href="/clients"
        className="inline-flex items-center gap-1 text-xs font-medium text-ink-subtle hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Todos los clientes
      </Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{client.legal_name}</h1>
          {client.trade_name && <p className="mt-0.5 text-sm text-ink-subtle">{client.trade_name}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <RegimenBadge regime={client.tax_regime} />
            <span className="text-ink-subtle">·</span>
            <span>
              NIT <span className="font-mono tabular-nums text-ink">{client.nit}</span>
            </span>
            {client.ica_city && (
              <>
                <span className="text-ink-subtle">·</span>
                <span>{client.ica_city}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <ClientTabsClient clientId={id} />

      <div className="mt-6">{children}</div>
    </div>
  );
}
