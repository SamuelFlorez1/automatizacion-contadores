import { formatDistanceToNowStrict, differenceInCalendarDays } from "date-fns";
import { es } from "date-fns/locale";

export function formatCompactCOP(n: number | string | null | undefined): string {
  if (n === null || n === undefined) return "—";
  const v = typeof n === "string" ? Number(n) : n;
  if (Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}k`;
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(v);
}

export function formatRelative(d: string | Date | null | undefined): string {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  const days = differenceInCalendarDays(date, new Date());
  if (days === 0) return "hoy";
  if (days === 1) return "mañana";
  if (days === -1) return "ayer";
  const prefix = days > 0 ? "en " : "hace ";
  return prefix + formatDistanceToNowStrict(date, { locale: es });
}

export function daysUntil(d: string | Date | null | undefined): number | null {
  if (!d) return null;
  const date = typeof d === "string" ? new Date(d) : d;
  return differenceInCalendarDays(date, new Date());
}

export type Delta = { text: string; tone: "up" | "down" | "flat" };

export function formatDelta(current: number, previous: number): Delta {
  if (!previous) return { text: "sin base", tone: "flat" };
  const pct = ((current - previous) / previous) * 100;
  const rounded = Math.abs(pct) < 0.1 ? 0 : pct;
  if (rounded === 0) return { text: "0%", tone: "flat" };
  return {
    text: `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}%`,
    tone: rounded > 0 ? "up" : "down",
  };
}

export function urgencyForDueDate(d: string | Date | null | undefined): "safe" | "soon" | "urgent" | "overdue" {
  const days = daysUntil(d);
  if (days === null) return "safe";
  if (days < 0) return "overdue";
  if (days <= 3) return "urgent";
  if (days <= 7) return "soon";
  return "safe";
}
