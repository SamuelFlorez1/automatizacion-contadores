"use client";

import { use, useState } from "react";
import { Download, FileBarChart2, Receipt, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { downloadPdf } from "@/lib/api";

const MONTHS: [string, string][] = [
  ["2026-07", "Julio 2026"],
  ["2026-08", "Agosto 2026"],
  ["2026-09", "Septiembre 2026"],
];

const IVA_PERIODS: [string, string][] = [
  ["jul-ago-2026", "Bimestre jul–ago 2026"],
  ["ene-abr-2026", "Cuatrimestre ene–abr 2026"],
  ["may-ago-2026", "Cuatrimestre may–ago 2026"],
];

export default function ReportsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [monthly, setMonthly] = useState(MONTHS[MONTHS.length - 1][0]);
  const [iva, setIva] = useState(IVA_PERIODS[0][0]);
  const [busy, setBusy] = useState<"monthly" | "iva" | null>(null);

  async function download(kind: "monthly" | "iva", path: string, filename: string) {
    setBusy(kind);
    try {
      await downloadPdf(path, filename);
      toast.success("PDF descargado", { description: filename });
    } catch (e) {
      toast.error("La descarga falló", { description: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ReportCard
        icon={<FileBarChart2 className="h-5 w-5" />}
        title="Reporte mensual"
        description="Estado de resultados, flujo de caja, top gastos y narrativa IA."
        options={MONTHS}
        selected={monthly}
        onSelect={setMonthly}
        busy={busy === "monthly"}
        onDownload={() => download("monthly", `/reports/monthly/${id}/${monthly}`, `mensual-${monthly}.pdf`)}
      />
      <ReportCard
        icon={<Receipt className="h-5 w-5" />}
        title="Formulario 300 (IVA)"
        description="Prellenado con casillas listas para revisión y presentación DIAN."
        options={IVA_PERIODS}
        selected={iva}
        onSelect={setIva}
        busy={busy === "iva"}
        onDownload={() => download("iva", `/reports/iva/${id}/${iva}`, `form300-${iva}.pdf`)}
      />
    </div>
  );
}

interface ReportCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  options: [string, string][];
  selected: string;
  onSelect: (v: string) => void;
  busy: boolean;
  onDownload: () => void;
}

function ReportCard({ icon, title, description, options, selected, onSelect, busy, onDownload }: ReportCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-brand-50 text-brand-700">
            {icon}
          </div>
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-ink-muted">Periodo</label>
          <Select value={selected} onValueChange={onSelect}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map(([v, label]) => (
                <SelectItem key={v} value={v}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={onDownload} disabled={busy} className="w-full">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {busy ? "Generando…" : "Descargar PDF"}
        </Button>
      </CardBody>
    </Card>
  );
}
