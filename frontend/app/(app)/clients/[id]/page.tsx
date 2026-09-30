import { FileText, Banknote, ClipboardList } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { PaymentBadge, MatchBadge, ObligationBadge } from "@/components/status-badge";
import { PaymentDonut } from "@/components/charts/payment-donut";
import { Sparkline } from "@/components/charts/sparkline";
import { formatCOP, formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

export default async function ClientOverview({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const [invoicesQ, bankQ, obligationsQ, sparkQ] = await Promise.all([
    supabase
      .from("invoices")
      .select("id, direction, supplier_name, customer_name, invoice_number, issue_date, total_cop, payment_status")
      .eq("client_id", id)
      .order("issue_date", { ascending: false })
      .limit(30),
    supabase
      .from("bank_transactions")
      .select("id, tx_date, description, amount, match_status")
      .eq("client_id", id)
      .order("tx_date", { ascending: false })
      .limit(12),
    supabase
      .from("tax_obligations")
      .select("id, kind, period_label, due_date, amount, status")
      .eq("client_id", id)
      .order("due_date", { ascending: true })
      .limit(6),
    supabase
      .from("invoices")
      .select("total_cop, issue_date, direction")
      .eq("client_id", id)
      .eq("direction", "emitida")
      .gte("issue_date", isoDaysAgo(90))
      .order("issue_date", { ascending: true }),
  ]);

  const invoices = invoicesQ.data || [];
  const bank = bankQ.data || [];
  const obligations = obligationsQ.data || [];

  // Donut: payment_status distribution across the last 30 invoices
  const paidCount = invoices.filter((i) => i.payment_status === "paid").length;
  const pendingCount = invoices.filter((i) => i.payment_status === "pending").length;
  const overdueCount = invoices.filter((i) => i.payment_status === "overdue").length;
  const otherCount = invoices.length - paidCount - pendingCount - overdueCount;
  const donutData = [
    { key: "paid", label: "Pagadas", value: paidCount, tone: "success" as const },
    { key: "pending", label: "Pendientes", value: pendingCount, tone: "warning" as const },
    { key: "overdue", label: "Vencidas", value: overdueCount, tone: "danger" as const },
    { key: "other", label: "Otras", value: otherCount, tone: "neutral" as const },
  ].filter((s) => s.value > 0);

  // Sparkline: weekly emitted totals
  const sparkRaw = (sparkQ.data || []) as { total_cop: number; issue_date: string }[];
  const weekMap = new Map<string, number>();
  for (const r of sparkRaw) {
    const d = new Date(r.issue_date);
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const key = monday.toISOString().slice(0, 10);
    weekMap.set(key, (weekMap.get(key) || 0) + Number(r.total_cop));
  }
  const spark = Array.from(weekMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([x, y]) => ({ x, y }));

  return (
    <div className="space-y-6">
      {/* KPI + mini chart row */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Distribución de pagos</CardTitle>
              <CardDescription>Últimas {invoices.length} facturas</CardDescription>
            </div>
          </CardHeader>
          <CardBody>
            {donutData.length === 0 ? (
              <EmptyState icon={FileText} title="Sin facturas aún" compact />
            ) : (
              <>
                <PaymentDonut data={donutData} />
                <div className="mt-3 flex flex-wrap gap-2 text-2xs text-ink-muted">
                  {donutData.map((s) => (
                    <div key={s.key} className="inline-flex items-center gap-1.5">
                      <span
                        className={cn(
                          "h-2 w-2 rounded-sm",
                          s.tone === "success" && "bg-success",
                          s.tone === "warning" && "bg-warning",
                          s.tone === "danger" && "bg-danger",
                          s.tone === "neutral" && "bg-ink-subtle"
                        )}
                      />
                      {s.label} <span className="font-mono tabular-nums text-ink">{s.value}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Facturación semanal</CardTitle>
              <CardDescription>Últimos 90 días · facturas emitidas</CardDescription>
            </div>
            <span className="font-mono text-lg font-semibold tabular-nums text-ink">
              {formatCOP(spark.reduce((s, r) => s + r.y, 0))}
            </span>
          </CardHeader>
          <CardBody>
            {spark.length === 0 ? (
              <EmptyState icon={Banknote} title="Sin actividad" compact />
            ) : (
              <Sparkline data={spark} />
            )}
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Facturas recientes</CardTitle>
              <CardDescription>Últimas 30 · emitidas y recibidas</CardDescription>
            </div>
          </CardHeader>
          <CardBody className="px-0 pb-0">
            {invoices.length === 0 ? (
              <div className="px-5 pb-5">
                <EmptyState icon={FileText} title="Sin facturas todavía" description="Sube una para empezar." compact />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-2xs uppercase tracking-wider text-ink-subtle">
                    <tr className="border-t border-line">
                      <th className="px-5 py-2 font-medium">Fecha</th>
                      <th className="py-2 font-medium">Número</th>
                      <th className="py-2 font-medium">Contraparte</th>
                      <th className="py-2 text-right font-medium">Total</th>
                      <th className="px-5 py-2 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.slice(0, 10).map((i) => (
                      <tr key={i.id} className="border-t border-line hover:bg-surface-sunken/60">
                        <td className="whitespace-nowrap px-5 py-2 text-ink-muted">{formatDate(i.issue_date)}</td>
                        <td className="py-2 font-mono tabular-nums text-ink">{i.invoice_number}</td>
                        <td className="max-w-[220px] truncate py-2 text-ink">
                          {i.direction === "recibida" ? i.supplier_name : i.customer_name}
                        </td>
                        <td className="py-2 text-right font-mono tabular-nums text-ink">{formatCOP(i.total_cop)}</td>
                        <td className="px-5 py-2">
                          <PaymentBadge status={i.payment_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Obligaciones fiscales</CardTitle>
              <CardDescription>Ordenadas por vencimiento</CardDescription>
            </div>
          </CardHeader>
          <CardBody className="px-0 pb-0">
            {obligations.length === 0 ? (
              <div className="px-5 pb-5">
                <EmptyState icon={ClipboardList} title="Sin obligaciones" compact />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-2xs uppercase tracking-wider text-ink-subtle">
                    <tr className="border-t border-line">
                      <th className="px-5 py-2 font-medium">Vence</th>
                      <th className="py-2 font-medium">Tipo</th>
                      <th className="py-2 font-medium">Periodo</th>
                      <th className="py-2 text-right font-medium">Monto</th>
                      <th className="px-5 py-2 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {obligations.map((o) => (
                      <tr key={o.id} className="border-t border-line hover:bg-surface-sunken/60">
                        <td className="whitespace-nowrap px-5 py-2 text-ink-muted">{formatDate(o.due_date)}</td>
                        <td className="py-2 font-medium uppercase text-ink">{o.kind}</td>
                        <td className="py-2 text-ink-muted">{o.period_label}</td>
                        <td className="py-2 text-right font-mono tabular-nums text-ink">{formatCOP(o.amount)}</td>
                        <td className="px-5 py-2">
                          <ObligationBadge status={o.status} />
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

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Movimientos bancarios recientes</CardTitle>
            <CardDescription>Últimos 12 movimientos</CardDescription>
          </div>
        </CardHeader>
        <CardBody className="px-0 pb-0">
          {bank.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState icon={Banknote} title="Sin movimientos" description="Sube el extracto bancario para verlos aquí." compact />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-2xs uppercase tracking-wider text-ink-subtle">
                  <tr className="border-t border-line">
                    <th className="px-5 py-2 font-medium">Fecha</th>
                    <th className="py-2 font-medium">Descripción</th>
                    <th className="py-2 text-right font-medium">Monto</th>
                    <th className="px-5 py-2 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {bank.map((b) => (
                    <tr key={b.id} className="border-t border-line hover:bg-surface-sunken/60">
                      <td className="whitespace-nowrap px-5 py-2 text-ink-muted">{formatDate(b.tx_date)}</td>
                      <td className="max-w-[420px] truncate py-2 text-ink">{b.description}</td>
                      <td
                        className={cn(
                          "py-2 text-right font-mono tabular-nums",
                          Number(b.amount) < 0 ? "text-danger" : "text-success"
                        )}
                      >
                        {formatCOP(b.amount)}
                      </td>
                      <td className="px-5 py-2">
                        <MatchBadge status={b.match_status} />
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

function isoDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}
