import { createClient } from "@/lib/supabase/server";
import { formatCOP, formatDate } from "@/lib/utils";
import { RunReconcileButton } from "./run-button";

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
      .select("id, match_type, confidence, matched_amount, reason, created_at, invoice_id, bank_transaction_id, invoices(invoice_number, supplier_name, customer_name), bank_transactions(tx_date, description, amount)")
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

  const matches = matchesQ.data || [];
  const reviews = reviewsQ.data || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Conciliación bancaria</h2>
          <p className="text-sm text-neutral-600">
            Matches automáticos entre extractos y facturas.
          </p>
        </div>
        <RunReconcileButton clientId={id} />
      </div>

      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">Matches ({matches.length})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="py-1">Fecha</th>
                <th>Extracto</th>
                <th>Factura</th>
                <th>Tipo</th>
                <th className="text-right">Monto</th>
                <th className="text-right">Confianza</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m: any) => (
                <tr key={m.id} className="border-t border-neutral-100">
                  <td className="py-1">{formatDate(m.bank_transactions?.tx_date)}</td>
                  <td className="max-w-[240px] truncate">{m.bank_transactions?.description}</td>
                  <td className="tabular-nums">{m.invoices?.invoice_number || "—"}</td>
                  <td className="uppercase">{m.match_type}</td>
                  <td className="text-right tabular-nums">{formatCOP(m.matched_amount)}</td>
                  <td className="text-right tabular-nums">{Number(m.confidence).toFixed(2)}</td>
                </tr>
              ))}
              {!matches.length && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-neutral-500">
                    Aún no hay conciliaciones. Corre el motor arriba.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold text-amber-700">
          Pendientes de revisión ({reviews.length})
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr>
                <th className="py-1">Fecha</th>
                <th>Descripción</th>
                <th>Referencia</th>
                <th className="text-right">Monto</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((r) => (
                <tr key={r.id} className="border-t border-neutral-100">
                  <td className="py-1">{formatDate(r.tx_date)}</td>
                  <td className="max-w-[320px] truncate">{r.description}</td>
                  <td className="truncate">{r.reference || "—"}</td>
                  <td className={`text-right tabular-nums ${Number(r.amount) < 0 ? "text-red-600" : "text-green-700"}`}>
                    {formatCOP(r.amount)}
                  </td>
                </tr>
              ))}
              {!reviews.length && (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-neutral-500">
                    Nada pendiente.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
