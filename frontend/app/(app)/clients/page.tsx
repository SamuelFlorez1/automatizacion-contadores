import Link from "next/link";
import { createClient } from "@/lib/supabase/server";

export default async function ClientsPage() {
  const supabase = await createClient();
  const { data: clients, error } = await supabase
    .from("clients")
    .select("id, legal_name, trade_name, nit, tax_regime, ica_city")
    .order("legal_name");

  return (
    <section>
      <h1 className="text-xl font-semibold">Clientes</h1>
      <p className="mt-1 text-sm text-neutral-600">
        Empresas atendidas por el despacho.
      </p>

      {error && (
        <p className="mt-4 text-sm text-red-600">Error cargando clientes: {error.message}</p>
      )}

      <div className="mt-6 overflow-hidden rounded-md border border-neutral-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 text-left text-xs uppercase text-neutral-500">
            <tr>
              <th className="px-4 py-2">Razón social</th>
              <th className="px-4 py-2">NIT</th>
              <th className="px-4 py-2">Régimen</th>
              <th className="px-4 py-2">Ciudad</th>
            </tr>
          </thead>
          <tbody>
            {(clients || []).map((c) => (
              <tr key={c.id} className="border-t border-neutral-100 hover:bg-neutral-50">
                <td className="px-4 py-2">
                  <Link href={`/clients/${c.id}`} className="text-neutral-900 hover:underline">
                    {c.legal_name}
                  </Link>
                  {c.trade_name && (
                    <div className="text-xs text-neutral-500">{c.trade_name}</div>
                  )}
                </td>
                <td className="px-4 py-2 tabular-nums">{c.nit}</td>
                <td className="px-4 py-2 capitalize">{c.tax_regime}</td>
                <td className="px-4 py-2">{c.ica_city || "—"}</td>
              </tr>
            ))}
            {!clients?.length && !error && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-neutral-500">
                  Sin clientes visibles.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
