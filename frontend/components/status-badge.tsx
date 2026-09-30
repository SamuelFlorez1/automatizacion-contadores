import { Badge } from "@/components/ui/badge";

type PaymentStatus = "paid" | "pending" | "overdue" | "partial" | string | null | undefined;
type MatchStatus = "matched" | "review" | "unmatched" | "partial" | string | null | undefined;
type ObligationStatus = "presentado" | "pendiente" | "en_proceso" | "vencido" | string | null | undefined;

const PAYMENT_MAP: Record<string, { label: string; tone: React.ComponentProps<typeof Badge>["tone"] }> = {
  paid: { label: "Pagada", tone: "success" },
  pending: { label: "Pendiente", tone: "warning" },
  overdue: { label: "Vencida", tone: "danger" },
  partial: { label: "Parcial", tone: "neutral" },
};

const MATCH_MAP: Record<string, { label: string; tone: React.ComponentProps<typeof Badge>["tone"] }> = {
  matched: { label: "Conciliada", tone: "success" },
  review: { label: "Revisar", tone: "warning" },
  unmatched: { label: "Sin match", tone: "neutral" },
  partial: { label: "Parcial", tone: "warning" },
};

const OBLIGATION_MAP: Record<string, { label: string; tone: React.ComponentProps<typeof Badge>["tone"] }> = {
  presentado: { label: "Presentado", tone: "success" },
  presented: { label: "Presentado", tone: "success" },
  pendiente: { label: "Pendiente", tone: "warning" },
  pending: { label: "Pendiente", tone: "warning" },
  en_proceso: { label: "En proceso", tone: "brand" },
  in_progress: { label: "En proceso", tone: "brand" },
  vencido: { label: "Vencido", tone: "danger" },
  overdue: { label: "Vencido", tone: "danger" },
};

export function PaymentBadge({ status }: { status: PaymentStatus }) {
  const cfg = PAYMENT_MAP[status || ""] || { label: status || "—", tone: "neutral" as const };
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

export function MatchBadge({ status }: { status: MatchStatus }) {
  const cfg = MATCH_MAP[status || ""] || { label: status || "—", tone: "neutral" as const };
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

export function ObligationBadge({ status }: { status: ObligationStatus }) {
  const cfg = OBLIGATION_MAP[status || ""] || { label: status || "—", tone: "neutral" as const };
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

export function RegimenBadge({ regime }: { regime: string | null | undefined }) {
  const r = (regime || "").toLowerCase();
  if (r.includes("simple")) return <Badge tone="warning">Régimen Simple</Badge>;
  if (r.includes("ordinar")) return <Badge tone="brand">Ordinario</Badge>;
  return <Badge tone="neutral">{regime || "—"}</Badge>;
}
