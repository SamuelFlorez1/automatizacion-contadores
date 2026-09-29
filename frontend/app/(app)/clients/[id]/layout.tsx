import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

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
    .select("id, legal_name, nit, tax_regime, ica_city")
    .eq("id", id)
    .maybeSingle();

  if (!client) notFound();

  const tabs = [
    { href: `/clients/${id}`, label: "Resumen" },
    { href: `/clients/${id}/reconciliation`, label: "Conciliación" },
    { href: `/clients/${id}/reports`, label: "Reportes" },
    { href: `/clients/${id}/upload`, label: "Cargar" },
  ];

  return (
    <div>
      <div className="mb-6">
        <Link href="/clients" className="text-xs text-neutral-500 hover:underline">
          ← Clientes
        </Link>
        <h1 className="mt-1 text-xl font-semibold">{client.legal_name}</h1>
        <p className="text-sm text-neutral-600">
          NIT {client.nit} · Régimen {client.tax_regime} · {client.ica_city || "—"}
        </p>
      </div>
      <nav className="mb-6 flex gap-1 border-b border-neutral-200 text-sm">
        {tabs.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="border-b-2 border-transparent px-3 py-2 text-neutral-600 hover:border-neutral-300 hover:text-neutral-900"
          >
            {t.label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
