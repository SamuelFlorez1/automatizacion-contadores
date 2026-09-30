"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { apiPost } from "@/lib/api";

export function RunReconcileButton({ clientId }: { clientId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onClick() {
    setBusy(true);
    try {
      const res = await apiPost(`/bank/reconcile/${clientId}`);
      const matched = res?.matched_count ?? res?.matches?.length ?? 0;
      toast.success("Conciliación completada", {
        description: `${matched} match${matched === 1 ? "" : "es"} generados.`,
      });
      router.refresh();
    } catch (e) {
      toast.error("No se pudo correr el motor", {
        description: (e as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button onClick={onClick} disabled={busy} variant="primary" size="md">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
      {busy ? "Corriendo…" : "Correr motor"}
    </Button>
  );
}
