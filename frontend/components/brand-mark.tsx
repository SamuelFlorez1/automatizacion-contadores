import { cn } from "@/lib/utils";

export function BrandMark({ className, showText = true }: { className?: string; showText?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative flex h-7 w-7 items-center justify-center rounded-[8px] bg-brand-600 shadow-[0_0_0_3px_hsl(var(--brand-100))]">
        <span aria-hidden className="absolute inset-0 rounded-[8px] bg-brand-600" />
        <span
          aria-hidden
          className="relative h-1.5 w-1.5 rounded-full bg-white/95 animate-pulse-dot"
        />
      </div>
      {showText && (
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight text-ink">Despacho</p>
          <p className="text-2xs text-ink-subtle">Automatización contable</p>
        </div>
      )}
    </div>
  );
}
