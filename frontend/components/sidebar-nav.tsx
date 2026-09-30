"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Inbox,
  Banknote,
  FileBarChart2,
  CalendarDays,
  ClipboardList,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Item =
  | { href: string; label: string; icon: LucideIcon; soon?: boolean }
  | { href: null; label: string; icon: LucideIcon; soon: true };

const GROUPS: { title: string; items: Item[] }[] = [
  {
    title: "General",
    items: [
      { href: "/dashboard", label: "Panel", icon: LayoutDashboard },
      { href: "/clients", label: "Clientes", icon: Users },
    ],
  },
  {
    title: "Operación",
    items: [
      { href: null, label: "Bandeja", icon: Inbox, soon: true },
      { href: null, label: "Conciliación", icon: Banknote, soon: true },
      { href: null, label: "Reportes", icon: FileBarChart2, soon: true },
    ],
  },
  {
    title: "Fiscal",
    items: [
      { href: null, label: "Calendario DIAN", icon: CalendarDays, soon: true },
      { href: null, label: "Obligaciones", icon: ClipboardList, soon: true },
    ],
  },
  {
    title: "Configuración",
    items: [{ href: null, label: "Ajustes", icon: Settings, soon: true }],
  },
];

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
      {GROUPS.map((group) => (
        <div key={group.title}>
          <div className="mb-1 px-2 text-2xs font-semibold uppercase tracking-wider text-ink-subtle">
            {group.title}
          </div>
          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.label}>
                <NavItem item={item} active={item.href ? isActive(pathname, item.href) : false} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard";
  return pathname === href || pathname.startsWith(href + "/");
}

function NavItem({ item, active }: { item: Item; active: boolean }) {
  const Icon = item.icon;
  const inner = (
    <div
      className={cn(
        "group relative flex items-center gap-2.5 rounded-[8px] px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-brand-50 text-brand-700"
          : "text-ink-muted hover:bg-surface-sunken hover:text-ink",
        item.soon && "cursor-not-allowed"
      )}
    >
      {active && (
        <span
          aria-hidden
          className="absolute -left-3 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-600"
        />
      )}
      <Icon
        className={cn("h-4 w-4 shrink-0", active ? "text-brand-600" : "text-ink-subtle group-hover:text-ink-muted")}
        strokeWidth={2}
      />
      <span className="flex-1 truncate">{item.label}</span>
      {item.soon && (
        <span className="rounded bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-subtle">
          pronto
        </span>
      )}
    </div>
  );

  if (item.soon || !item.href) return <div aria-disabled>{inner}</div>;
  return <Link href={item.href}>{inner}</Link>;
}
