import { createClient } from "@/lib/supabase/server";
import { formatCOP, formatDate } from "@/lib/utils";

export default async function ClientOverview({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const [invoicesQ, bankQ, obligationsQ] = await Promise.all([
    supabase
      .from("invoices")
      .select("id, direction, supplier_name, customer_name, invoice_number, issue_date, total_cop, payment_status, puc_account")
      .eq("client_id", id)
      .order("issue_date", { ascending: false })
      .limit(20),
    supabase
      .from("bank_transactions")
      .select("id, tx_date, description, amount, match_status")
      .eq("client_id", id)
      .order("tx_date", { ascending: false })
      .limit(15),
    supabase
      .from("tax_obligations")
      .select("id, kind, period_label, due_date, amount, status")
      .eq("client_id", id)
      .order("due_date", { ascending: true }),
  ]);

  const invoices = invoicesQ.data || [];
  const bank = bankQ.data || [];
  const obligations = obligationsQ.data || [];

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card title="Facturas recientes">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-neutral-500">
            <tr>
              <th className="py-1">Fecha</th>
              <th>Número</th>
              <th>Contraparte</th>
              <th className="text-right">Total</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((i) => (
              <tr key={i.id} className="border-t border-neutral-100">
                <td className="py-1">{formatDate(i.issue_date)}</td>
                <td className="tabular-nums">{i.invoice_number}</td>
                <td className="truncate">
                  {i.direction === "recibida" ? i.supplier_name : i.customer_name}
                </td>
                <td className="text-right tabular-nums">{formatCOP(i.total_cop)}</td>
                <td>
                  <Badge tone={i.payment_status === "paid" ? "green" : "gray"}>
                    {i.payment_status}
                  </Badge>
                </td>
              </tr>
            ))}
            {!invoices.length && <EmptyRow cols={5} />}
          </tbody>
        </table>
      </Card>

      <Card title="Obligaciones fiscales">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-neutral-500">
            <tr>
              <th className="py-1">Vence</th>
              <th>Tipo</th>
              <th>Periodo</th>
              <th className="text-right">Monto</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {obligations.map((o) => (
              <tr key={o.id} className="border-t border-neutral-100">
                <td className="py-1">{formatDate(o.due_date)}</td>
                <td className="uppercase">{o.kind}</td>
                <td>{o.period_label}</td>
                <td className="text-right tabular-nums">{formatCOP(o.amount)}</td>
                <td>
                  <Badge tone={o.status === "presentado" ? "green" : "amber"}>{o.status}</Badge>
                </td>
              </tr>
            ))}
            {!obligations.length && <EmptyRow cols={5} />}
          </tbody>
        </table>
      </Card>

      <Card title="Movimientos bancarios">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-neutral-500">
            <tr>
              <th className="py-1">Fecha</th>
              <th>Descripción</th>
              <th className="text-right">Monto</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {bank.map((b) => (
              <tr key={b.id} className="border-t border-neutral-100">
                <td className="py-1">{formatDate(b.tx_date)}</td>
                <td className="truncate">{b.description}</td>
                <td className={`text-right tabular-nums ${Number(b.amount) < 0 ? "text-red-600" : "text-green-700"}`}>
                  {formatCOP(b.amount)}
                </td>
                <td>
                  <Badge tone={b.match_status === "matched" ? "green" : b.match_status === "review" ? "amber" : "gray"}>
                    {b.match_status}
                  </Badge>
                </td>
              </tr>
            ))}
            {!bank.length && <EmptyRow cols={4} />}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-neutral-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-neutral-700">{title}</h2>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

function Badge({ tone, children }: { tone: "green" | "amber" | "gray"; children: React.ReactNode }) {
  const cls =
    tone === "green"
      ? "bg-green-100 text-green-800"
      : tone === "amber"
      ? "bg-amber-100 text-amber-800"
      : "bg-neutral-100 text-neutral-700";
  return <span className={`rounded px-2 py-0.5 text-xs ${cls}`}>{children}</span>;
}

function EmptyRow({ cols }: { cols: number }) {
  return (
    <tr>
      <td colSpan={cols} className="py-4 text-center text-neutral-500">
        Sin datos.
      </td>
    </tr>
  );
}
