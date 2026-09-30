import { AlertTriangle, CheckCircle2, Banknote } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { ConfidenceBar } from "@/components/confidence-bar";
import { Button } from "@/components/ui/button";
import { formatCOP, formatDate } from "@/lib/utils";
import { RunReconcileButton } from "./run-button";
import { cn } from "@/lib/utils";

type MatchRow = {
  id: string;
  match_type: string;
  confidence: number;
  matched_amount: number;
  reason: string | null;
  created_at: string;
  invoices: { invoice_number: string; supplier_name: string | null; customer_name: string | null } | null;
  bank_transactions: { tx_date: string; description: string; amount: number } | null;
};

export default async function ReconciliationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const [matchesQ, reviewsQ] = await Promise.all([
    supabase
      .from("reconciliation_matches")
      .select(
        "id, match_type, confidence, matched_amount, reason, created_at, invoices(invoice_number, supplier_name, customer_name), bank_transactions(tx_date, description, amount)"
      )
      .eq("client_id", id)
      .order("created_at", { ascending: false })
      .limit(50),
    supabase
      .from("bank_transactions")
      .select("id, tx_date, description, amount, reference")
      .eq("client_id", id)
      .in("match_status", ["review", "unmatched"])
      .order("tx_date", { ascending: false })
      .limit(50),
  ]);

  const matches = (matchesQ.data as MatchRow[] | null) || [];
  const reviews = reviewsQ.data || [];
  const attention = reviews.length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-ink">Conciliación bancaria</h2>
            {attention > 0 && (
              <Badge tone="danger">
                <AlertTriangle className="h-3 w-3" />
                {attention} necesitan atención
              </Badge>
            )}
            {attention === 0 && matches.length > 0 && (
              <Badge tone="success">
                <CheckCircle2 className="h-3 w-3" />
                al día
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-ink-muted">
            Cruce automático entre extractos bancarios y facturas registradas.
          </p>
        </div>
        <RunReconcileButton clientId={id} />
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Matches</CardTitle>
            <CardDescription>{matches.length} generados por el motor</CardDescription>
          </div>
        </CardHeader>
        <CardBody className="px-0 pb-0">
          {matches.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState
                icon={Banknote}
                title="Aún no hay conciliaciones"
                description="Corre el motor para cruzar extractos y facturas."
                compact
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-2xs uppercase tracking-wider text-ink-subtle">
                  <tr className="border-t border-line">
                    <th className="px-5 py-2 font-medium">Fecha</th>
                    <th className="py-2 font-medium">Extracto</th>
                    <th className="py-2 font-medium">Factura</th>
                    <th className="py-2 font-medium">Tipo</th>
                    <th className="py-2 text-right font-medium">Monto</th>
                    <th className="px-5 py-2 font-medium">Confianza</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m) => (
                    <tr key={m.id} className="border-t border-line hover:bg-surface-sunken/60">
                      <td className="whitespace-nowrap px-5 py-2 text-ink-muted">
                        {formatDate(m.bank_transactions?.tx_date)}
                      </td>
                      <td className="max-w-[260px] truncate py-2 text-ink">
                        {m.bank_transactions?.description || "—"}
                      </td>
                      <td className="py-2 font-mono tabular-nums text-ink">
                        {m.invoices?.invoice_number || "—"}
                      </td>
                      <td className="py-2">
                        <Badge tone="brand">{m.match_type}</Badge>
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink">
                        {formatCOP(m.matched_amount)}
                      </td>
                      <td className="px-5 py-2">
                        <ConfidenceBar value={Number(m.confidence)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      <Card className={cn(attention > 0 && "border-warning/40")}>
        <CardHeader>
          <div>
            <CardTitle className="text-warning-fg">Pendientes de revisión</CardTitle>
            <CardDescription>{attention} transacción(es) sin match automático</CardDescription>
          </div>
        </CardHeader>
        <CardBody className="px-0 pb-0">
          {reviews.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState icon={CheckCircle2} title="Todo conciliado" compact />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-2xs uppercase tracking-wider text-ink-subtle">
                  <tr className="border-t border-line">
                    <th className="px-5 py-2 font-medium">Fecha</th>
                    <th className="py-2 font-medium">Descripción</th>
                    <th className="py-2 font-medium">Referencia</th>
                    <th className="py-2 text-right font-medium">Monto</th>
                    <th className="px-5 py-2 font-medium text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {reviews.map((r) => (
                    <tr key={r.id} className="border-t border-line hover:bg-surface-sunken/60">
                      <td className="whitespace-nowrap px-5 py-2 text-ink-muted">{formatDate(r.tx_date)}</td>
                      <td className="max-w-[320px] truncate py-2 text-ink">{r.description}</td>
                      <td className="max-w-[160px] truncate py-2 text-ink-muted">{r.reference || "—"}</td>
                      <td
                        className={cn(
                          "py-2 text-right font-mono tabular-nums",
                          Number(r.amount) < 0 ? "text-danger" : "text-success"
                        )}
                      >
                        {formatCOP(r.amount)}
                      </td>
                      <td className="px-5 py-2 text-right">
                        <div className="inline-flex items-center gap-1">
                          <Button size="sm" variant="secondary" disabled title="Próximamente">
                            Buscar match
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
