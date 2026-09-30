"use client";

import { useRouter } from "next/navigation";
import { ChevronsUpDown, LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { createClient } from "@/lib/supabase/client";

interface UserMenuProps {
  name: string;
  email: string;
  role?: string | null;
}

const ROLE_LABEL: Record<string, string> = {
  firm_admin: "Admin",
  accountant: "Contador",
  client: "Cliente",
};

export function UserMenu({ name, email, role }: UserMenuProps) {
  const router = useRouter();
  const initials = name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-[8px] p-2 text-left hover:bg-surface-sunken">
          <Avatar>
            <AvatarFallback>{initials || "U"}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{name}</p>
            <p className="truncate text-2xs text-ink-subtle">{role ? ROLE_LABEL[role] || role : email}</p>
          </div>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-ink-subtle" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut} className="text-danger focus:text-danger">
          <LogOut className="h-4 w-4" />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
