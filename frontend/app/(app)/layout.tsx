import { redirect } from "next/navigation";
import { Search } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { SidebarNav } from "@/components/sidebar-nav";
import { BrandMark } from "@/components/brand-mark";
import { MobileSidebar } from "@/components/mobile-sidebar";
import { UserMenu } from "./_components/user-menu";
import { Breadcrumbs } from "./_components/breadcrumbs";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("users")
    .select("full_name, email, role")
    .eq("id", user.id)
    .maybeSingle();

  const name = profile?.full_name || user.email || "Usuario";
  const menu = <UserMenu name={name} email={profile?.email || user.email || ""} role={profile?.role} />;

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[260px_1fr]">
      <aside className="hidden flex-col border-r border-line bg-surface-card lg:flex">
        <div className="border-b border-line px-5 py-4">
          <BrandMark />
        </div>
        <SidebarNav />
        <div className="border-t border-line p-2">{menu}</div>
      </aside>

      <div className="flex flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-line bg-surface-card/80 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-3">
            <MobileSidebar footer={menu} />
            <div className="lg:hidden">
              <BrandMark showText={false} />
            </div>
            <Breadcrumbs />
          </div>
          <div className="flex items-center gap-2">
            <div className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-subtle" />
              <input
                type="search"
                placeholder="Buscar…"
                className="h-8 w-56 rounded-[8px] border border-line bg-surface pl-8 pr-12 text-sm text-ink placeholder:text-ink-subtle focus-visible:border-brand-600 focus-visible:outline-none"
              />
              <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-line bg-surface-card px-1.5 py-0.5 text-[10px] font-medium text-ink-subtle">
                ⌘K
              </kbd>
            </div>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>
    </div>
  );
}
