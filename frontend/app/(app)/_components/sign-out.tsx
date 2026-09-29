"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export function SignOutButton() {
  const router = useRouter();
  async function onClick() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }
  return (
    <button
      onClick={onClick}
      className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs hover:bg-neutral-100"
    >
      Cerrar sesión
    </button>
  );
}
