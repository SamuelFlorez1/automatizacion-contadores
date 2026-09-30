"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { FileText, Banknote, Loader2, Upload as UploadIcon } from "lucide-react";
import { toast } from "sonner";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dropzone } from "@/components/dropzone";
import { apiPost } from "@/lib/api";

export default function UploadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [docFile, setDocFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"doc" | "bank" | null>(null);

  async function submit(kind: "doc" | "bank") {
    const file = kind === "doc" ? docFile : bankFile;
    if (!file) return;
    setBusy(kind);
    try {
      const fd = new FormData();
      fd.append("client_id", id);
      fd.append("file", file);
      const endpoint = kind === "doc" ? "/ingest/upload" : "/bank/upload";
      const res = await apiPost(endpoint, fd);
      if (kind === "doc") {
        toast.success("Documento cargado", {
          description: `${res?.status || "procesado"} · ${res?.document_id || ""}`,
        });
        setDocFile(null);
      } else {
        toast.success("Extracto cargado", {
          description: `${res?.inserted ?? 0} movimientos importados.`,
        });
        setBankFile(null);
      }
      router.refresh();
    } catch (e) {
      toast.error("Falló la carga", { description: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-brand-50 text-brand-700">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Cargar documento</CardTitle>
              <CardDescription>Factura XML UBL, PDF o imagen. Extracción automática.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <Dropzone
            accept=".xml,.pdf,.png,.jpg,.jpeg,.webp"
            hint="XML UBL, PDF, PNG, JPG, WEBP"
            file={docFile}
            onFile={setDocFile}
            disabled={busy !== null}
          />
          <Button onClick={() => submit("doc")} disabled={!docFile || busy !== null} className="w-full">
            {busy === "doc" ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadIcon className="h-4 w-4" />}
            {busy === "doc" ? "Procesando…" : "Subir documento"}
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-brand-50 text-brand-700">
              <Banknote className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Cargar extracto bancario</CardTitle>
              <CardDescription>CSV normalizado: fecha, descripción, monto, referencia.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <Dropzone
            accept=".csv"
            hint="Archivo CSV con columnas normalizadas"
            file={bankFile}
            onFile={setBankFile}
            disabled={busy !== null}
          />
          <Button onClick={() => submit("bank")} disabled={!bankFile || busy !== null} className="w-full">
            {busy === "bank" ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadIcon className="h-4 w-4" />}
            {busy === "bank" ? "Importando…" : "Subir CSV"}
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
