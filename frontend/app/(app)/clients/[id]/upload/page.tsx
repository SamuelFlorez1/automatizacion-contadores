"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";

export default function UploadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [msgDoc, setMsgDoc] = useState<string | null>(null);
  const [msgBank, setMsgBank] = useState<string | null>(null);
  const [busy, setBusy] = useState<"doc" | "bank" | null>(null);

  async function onDoc(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const file = (form.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file) return;
    setBusy("doc");
    setMsgDoc(null);
    try {
      const fd = new FormData();
      fd.append("client_id", id);
      fd.append("file", file);
      const res = await apiPost("/ingest/upload", fd);
      setMsgDoc(`OK — documento ${res?.document_id || ""} (${res?.status || "ok"})`);
      form.reset();
      router.refresh();
    } catch (err) {
      setMsgDoc(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function onBank(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const file = (form.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file) return;
    setBusy("bank");
    setMsgBank(null);
    try {
      const fd = new FormData();
      fd.append("client_id", id);
      fd.append("file", file);
      const res = await apiPost("/bank/upload", fd);
      setMsgBank(`OK — ${res?.inserted ?? 0} movimientos cargados.`);
      form.reset();
      router.refresh();
    } catch (err) {
      setMsgBank(`Error: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <form onSubmit={onDoc} className="rounded-md border border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Cargar documento</h2>
        <p className="mt-1 text-xs text-neutral-600">
          Factura XML UBL, PDF o imagen. Se procesa vía extracción (Fase 2).
        </p>
        <input
          type="file"
          name="file"
          required
          accept=".xml,.pdf,.png,.jpg,.jpeg,.webp"
          className="mt-4 w-full text-sm"
        />
        <button
          disabled={busy === "doc"}
          className="mt-4 rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-60"
        >
          {busy === "doc" ? "Subiendo…" : "Subir documento"}
        </button>
        {msgDoc && <p className="mt-3 text-xs text-neutral-700">{msgDoc}</p>}
      </form>

      <form onSubmit={onBank} className="rounded-md border border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Cargar extracto bancario</h2>
        <p className="mt-1 text-xs text-neutral-600">
          CSV con columnas normalizadas (fecha, descripción, monto, ref).
        </p>
        <input type="file" name="file" required accept=".csv" className="mt-4 w-full text-sm" />
        <button
          disabled={busy === "bank"}
          className="mt-4 rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-60"
        >
          {busy === "bank" ? "Subiendo…" : "Subir CSV"}
        </button>
        {msgBank && <p className="mt-3 text-xs text-neutral-700">{msgBank}</p>}
      </form>
    </div>
  );
}
