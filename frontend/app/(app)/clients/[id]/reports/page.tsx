"use client";

import { use, useState } from "react";
import { downloadPdf } from "@/lib/api";

const MONTHS = [
  ["2026-07", "Julio 2026"],
  ["2026-08", "Agosto 2026"],
  ["2026-09", "Septiembre 2026"],
];

const IVA_PERIODS = [
  ["jul-ago-2026", "Bimestre jul-ago 2026"],
  ["ene-abr-2026", "Cuatrimestre ene-abr 2026"],
  ["may-ago-2026", "Cuatrimestre may-ago 2026"],
];

export default function ReportsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(path: string, filename: string) {
    setBusy(filename);
    setError(null);
    try {
      await downloadPdf(path, filename);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Reporte mensual</h2>
        <p className="mt-1 text-xs text-neutral-600">
          Estado de resultados, flujo de caja, top 10 gastos y análisis IA.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {MONTHS.map(([p, label]) => (
            <button
              key={p}
              disabled={busy !== null}
              onClick={() => download(`/reports/monthly/${id}/${p}`, `mensual-${p}.pdf`)}
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:bg-neutral-100 disabled:opacity-50"
            >
              {busy === `mensual-${p}.pdf` ? "Descargando…" : label}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Formulario 300 (IVA)</h2>
        <p className="mt-1 text-xs text-neutral-600">Prellenado listo para revisión.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {IVA_PERIODS.map(([p, label]) => (
            <button
              key={p}
              disabled={busy !== null}
              onClick={() => download(`/reports/iva/${id}/${p}`, `form300-${p}.pdf`)}
              className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:bg-neutral-100 disabled:opacity-50"
            >
              {busy === `form300-${p}.pdf` ? "Descargando…" : label}
            </button>
          ))}
        </div>
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
