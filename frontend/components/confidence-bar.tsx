import { cn } from "@/lib/utils";

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone =
    value >= 0.8 ? "bg-success" : value >= 0.5 ? "bg-warning" : "bg-danger";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-sunken">
        <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-2xs tabular-nums text-ink-muted">{value.toFixed(2)}</span>
    </div>
  );
}
