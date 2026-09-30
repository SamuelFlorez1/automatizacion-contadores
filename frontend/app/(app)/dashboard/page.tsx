import Link from "next/link";
import { Banknote, TrendingUp, Receipt, AlarmClock, ArrowRight, FileText, Calendar } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { KpiCard } from "@/components/kpi-card";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { IncomeExpenseBars } from "@/components/charts/income-expense-bars";
import { formatCompactCOP, formatDelta, formatRelative, urgencyForDueDate, daysUntil } from "@/lib/format";
import { formatCOP, formatDate } from "@/lib/utils";

const MONTH_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function clientName(c: { legal_name: string } | { legal_name: string }[] | null | undefined): string | null {
  if (!c) return null;
  if (Array.isArray(c)) return c[0]?.legal_name ?? null;
  return c.legal_name;
}

export default async function DashboardPage() {
  const supabase = await createClient();
  const today = new Date();
  const sixMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 5, 1);
  const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const startOfPrevMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const startOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);

  const [invoicesQ, obligationsQ, recentInvoicesQ] = await Promise.all([
    supabase
      .from("invoices")
      .select("direction, total_cop, issue_date, payment_status, client_id")
      .gte("issue_date", sixMonthsAgo.toISOString().slice(0, 10)),
    supabase
      .from("tax_obligations")
      .select("id, client_id, kind, period_label, due_date, amount, status")
      .in("status", ["pendiente", "pending"])
      .order("due_date", { ascending: true })
      .limit(6),
    supabase
      .from("invoices")
      .select("id, direction, supplier_name, customer_name, invoice_number, total_cop, issue_date, client_id, clients(legal_name)")
      .order("issue_date", { ascending: false })
      .limit(6),
  ]);

  const invoices = invoicesQ.data || [];
  const obligations = obligationsQ.data || [];
  const recent = ((recentInvoicesQ.data || []) as unknown) as Array<{
    id: string;
    direction: string;
    supplier_name: string | null;
    customer_name: string | null;
    invoice_number: string;
    total_cop: number;
    issue_date: string;
    clients: { legal_name: string } | { legal_name: string }[] | null;
  }>;

  // KPIs
  let incomeThisMonth = 0, expenseThisMonth = 0, incomePrevMonth = 0, expensePrevMonth = 0;
  for (const inv of invoices) {
    const d = new Date(inv.issue_date);
    const amt = Number(inv.total_cop) || 0;
    if (d >= startOfMonth && d < startOfNextMonth) {
      if (inv.direction === "emitida") incomeThisMonth += amt;
      else expenseThisMonth += amt;
    } else if (d >= startOfPrevMonth && d < startOfMonth) {
      if (inv.direction === "emitida") incomePrevMonth += amt;
      else expensePrevMonth += amt;
    }
  }

  // Pending IVA total from obligations (approx)
  const ivaPending = obligations
    .filter((o) => (o.kind || "").toLowerCase().includes("iva"))
    .reduce((s, o) => s + (Number(o.amount) || 0), 0);

  const nextObligation = obligations[0];
  const daysToNext = nextObligation ? daysUntil(nextObligation.due_date) : null;

  // Bar chart: last 6 months aggregated
  const byMonth = new Map<string, { month: string; ingresos: number; gastos: number }>();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
    byMonth.set(monthKey(d), { month: MONTH_ES[d.getMonth()], ingresos: 0, gastos: 0 });
  }
  for (const inv of invoices) {
    const d = new Date(inv.issue_date);
    const key = monthKey(d);
    const row = byMonth.get(key);
    if (!row) continue;
    const amt = Number(inv.total_cop) || 0;
    if (inv.direction === "emitida") row.ingresos += amt;
    else row.gastos += amt;
  }
  const chartData = Array.from(byMonth.values());

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Panel</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Resumen de la operación del despacho — {formatDate(today.toISOString())}
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Facturado este mes"
          value={formatCompactCOP(incomeThisMonth)}
          icon={TrendingUp}
          delta={formatDelta(incomeThisMonth, incomePrevMonth)}
          hint="vs mes anterior"
          emphasis="brand"
        />
        <KpiCard
          label="Gastos este mes"
          value={formatCompactCOP(expenseThisMonth)}
          icon={Banknote}
          delta={formatDelta(expenseThisMonth, expensePrevMonth)}
          hint="vs mes anterior"
        />
        <KpiCard
          label="IVA por pagar"
          value={formatCompactCOP(ivaPending)}
          icon={Receipt}
          hint={`${obligations.filter((o) => (o.kind || "").toLowerCase().includes("iva")).length} obligación(es)`}
        />
        <KpiCard
          label="Próxima obligación"
          value={daysToNext !== null ? (daysToNext >= 0 ? `${daysToNext}d` : "vencida") : "—"}
          icon={AlarmClock}
          hint={nextObligation ? `${(nextObligation.kind || "").toUpperCase()} · ${nextObligation.period_label}` : "sin pendientes"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Ingresos vs gastos</CardTitle>
              <CardDescription>Últimos 6 meses, todas las empresas</CardDescription>
            </div>
          </CardHeader>
          <CardBody>
            <IncomeExpenseBars data={chartData} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Próximas obligaciones DIAN</CardTitle>
              <CardDescription>Ordenadas por vencimiento</CardDescription>
            </div>
          </CardHeader>
          <CardBody className="pt-1">
            {obligations.length === 0 ? (
              <EmptyState
                icon={Calendar}
                title="Nada pendiente"
                description="Cuando entren obligaciones aparecerán aquí."
                compact
              />
            ) : (
              <ul className="divide-y divide-line">
                {obligations.map((o) => {
                  const urgency = urgencyForDueDate(o.due_date);
                  const tone =
                    urgency === "overdue" || urgency === "urgent"
                      ? "danger"
                      : urgency === "soon"
                      ? "warning"
                      : "success";
                  return (
                    <li key={o.id} className="flex items-center justify-between gap-3 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink">
                          {(o.kind || "").toUpperCase()} · {o.period_label}
                        </p>
                        <p className="text-xs text-ink-subtle">
                          Vence {formatDate(o.due_date)} · {formatRelative(o.due_date)}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-mono text-sm tabular-nums text-ink">
                          {formatCOP(o.amount)}
                        </span>
                        <Badge tone={tone as "danger" | "warning" | "success"}>
                          {urgency === "overdue" ? "vencida" : urgency === "urgent" ? "urgente" : urgency === "soon" ? "pronto" : "a tiempo"}
                        </Badge>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Actividad reciente</CardTitle>
            <CardDescription>Últimas facturas procesadas</CardDescription>
          </div>
          <Link
            href="/clients"
            className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:text-brand-600"
          >
            Ver clientes
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </CardHeader>
        <CardBody>
          {recent.length === 0 ? (
            <EmptyState icon={FileText} title="Sin actividad todavía" description="Sube una factura para empezar." compact />
          ) : (
            <ul className="divide-y divide-line">
              {recent.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div
                      className={
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full " +
                        (r.direction === "emitida" ? "bg-success-soft text-success-fg" : "bg-brand-50 text-brand-700")
                      }
                    >
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">
                        {r.direction === "emitida" ? "Factura emitida" : "Factura recibida"} · {r.invoice_number}
                      </p>
                      <p className="truncate text-xs text-ink-subtle">
                        {clientName(r.clients) || "—"} · {r.direction === "emitida" ? r.customer_name : r.supplier_name}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-right">
                    <div>
                      <p className="font-mono text-sm tabular-nums text-ink">{formatCOP(r.total_cop)}</p>
                      <p className="text-2xs text-ink-subtle">{formatRelative(r.issue_date)}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
