"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, Banknote, FileBarChart2, Upload, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function ClientTabsClient({ clientId }: { clientId: string }) {
  const pathname = usePathname();
  const base = `/clients/${clientId}`;
  const tabs: { href: string; label: string; icon: LucideIcon; match: (p: string) => boolean }[] = [
    { href: base, label: "Resumen", icon: FileText, match: (p) => p === base },
    { href: `${base}/reconciliation`, label: "Conciliación", icon: Banknote, match: (p) => p.startsWith(`${base}/reconciliation`) },
    { href: `${base}/reports`, label: "Reportes", icon: FileBarChart2, match: (p) => p.startsWith(`${base}/reports`) },
    { href: `${base}/upload`, label: "Cargar", icon: Upload, match: (p) => p.startsWith(`${base}/upload`) },
  ];

  return (
    <div className="mt-6 border-b border-line">
      <nav className="-mb-px flex gap-1 overflow-x-auto">
        {tabs.map((t) => {
          const active = t.match(pathname);
          const Icon = t.icon;
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                "inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-ink-muted hover:border-line-strong hover:text-ink"
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-brand-600" : "text-ink-subtle")} />
              {t.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
