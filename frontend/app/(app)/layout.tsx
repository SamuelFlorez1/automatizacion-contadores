import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SignOutButton } from "./_components/sign-out";

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

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="border-r border-neutral-200 bg-white px-4 py-6">
        <div className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Despacho
        </div>
        <nav className="mt-6 space-y-1 text-sm">
          <Link href="/clients" className="block rounded px-3 py-2 hover:bg-neutral-100">
            Clientes
          </Link>
        </nav>
      </aside>
      <div className="flex flex-col">
        <header className="flex h-14 items-center justify-between border-b border-neutral-200 bg-white px-6">
          <div className="text-sm text-neutral-600">
            {profile?.full_name || user.email}
            {profile?.role && (
              <span className="ml-2 rounded bg-neutral-100 px-2 py-0.5 text-xs uppercase text-neutral-700">
                {profile.role}
              </span>
            )}
          </div>
          <SignOutButton />
        </header>
        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}
