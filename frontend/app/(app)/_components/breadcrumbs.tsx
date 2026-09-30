"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

const LABELS: Record<string, string> = {
  dashboard: "Panel",
  clients: "Clientes",
  reconciliation: "Conciliación",
  reports: "Reportes",
  upload: "Cargar",
};

export function Breadcrumbs({ clientLabel }: { clientLabel?: string }) {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length) return null;

  const crumbs = parts.map((p, i) => {
    const href = "/" + parts.slice(0, i + 1).join("/");
    let label = LABELS[p] || p;
    if (/^[0-9a-f]{8}-[0-9a-f-]{20,}$/i.test(p)) {
      label = clientLabel || "Cliente";
    }
    return { href, label, isLast: i === parts.length - 1 };
  });

  return (
    <nav aria-label="Breadcrumb" className="hidden items-center gap-1 text-xs text-ink-subtle md:flex">
      {crumbs.map((c, i) => (
        <span key={c.href} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3 w-3 text-ink-subtle/70" />}
          {c.isLast ? (
            <span className="font-medium text-ink">{c.label}</span>
          ) : (
            <Link href={c.href} className="hover:text-ink">
              {c.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}
