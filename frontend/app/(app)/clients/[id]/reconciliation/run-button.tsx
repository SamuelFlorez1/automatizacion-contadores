"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiPost } from "@/lib/api";

export function RunReconcileButton({ clientId }: { clientId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await apiPost(`/bank/reconcile/${clientId}`);
      const matched = (res?.exact ?? 0) + (res?.fuzzy ?? 0) + (res?.transfer ?? 0);
      setMsg(`OK — ${matched} matches, ${res?.review ?? 0} en revisión, ${res?.unmatched ?? 0} sin conciliar.`);
      router.refresh();
    } catch (e) {
      setMsg(`Error: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      {msg && <span className="text-xs text-neutral-600">{msg}</span>}
      <button
        onClick={run}
        disabled={loading}
        className="rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-60"
      >
        {loading ? "Conciliando…" : "Correr conciliación"}
      </button>
    </div>
  );
}
