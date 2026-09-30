"use client";

import * as React from "react";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarNav } from "@/components/sidebar-nav";
import { BrandMark } from "@/components/brand-mark";

export function MobileSidebar({ footer }: { footer: React.ReactNode }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button
          className="inline-flex h-9 w-9 items-center justify-center rounded-[8px] border border-line bg-surface-card text-ink-muted lg:hidden"
          aria-label="Abrir menú"
        >
          <Menu className="h-4 w-4" />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="flex flex-col">
        <div className="border-b border-line px-4 py-4">
          <BrandMark />
        </div>
        <SidebarNav />
        <div className="border-t border-line p-2">{footer}</div>
      </SheetContent>
    </Sheet>
  );
}
