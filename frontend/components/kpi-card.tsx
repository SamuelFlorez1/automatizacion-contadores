import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Delta } from "@/lib/format";

interface KpiCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  delta?: Delta;
  hint?: string;
  emphasis?: "default" | "brand";
}

export function KpiCard({ label, value, icon: Icon, delta, hint, emphasis = "default" }: KpiCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col justify-between rounded-card border border-line bg-surface-card p-5 shadow-card",
        emphasis === "brand" && "border-brand-200 bg-gradient-to-br from-brand-50/60 to-surface-card"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs font-medium text-ink-subtle">{label}</div>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-brand-50 text-brand-700">
            <Icon className="h-4 w-4" strokeWidth={2.2} />
          </div>
        )}
      </div>
      <div className="mt-3 font-mono text-2xl font-semibold tabular-nums tracking-tight text-ink">{value}</div>
      <div className="mt-2 flex items-center gap-2 text-xs">
        {delta && <DeltaChip delta={delta} />}
        {hint && <span className="text-ink-subtle">{hint}</span>}
      </div>
    </div>
  );
}

function DeltaChip({ delta }: { delta: Delta }) {
  const Icon = delta.tone === "up" ? ArrowUpRight : delta.tone === "down" ? ArrowDownRight : Minus;
  const cls =
    delta.tone === "up"
      ? "text-success"
      : delta.tone === "down"
      ? "text-danger"
      : "text-ink-subtle";
  return (
    <span className={cn("inline-flex items-center gap-0.5 font-medium", cls)}>
      <Icon className="h-3 w-3" strokeWidth={2.5} />
      {delta.text}
    </span>
  );
}
