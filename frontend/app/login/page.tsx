"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MessageSquareText, ScanLine, FileBarChart2 } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BrandMark } from "@/components/brand-mark";

function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(email
        ? "No pudimos iniciar sesión. Revisa tu correo y contraseña."
        : "Ingresa tu correo y contraseña para continuar.");
      return;
    }
    router.push(next);
    router.refresh();
  }

  function useDemo(demoEmail: string, demoPw: string) {
    setEmail(demoEmail);
    setPassword(demoPw);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="email">Correo</Label>
        <Input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          placeholder="tu@empresa.com"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="password">Contraseña</Label>
        <Input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder="••••••••"
        />
      </div>
      {error && (
        <p className="rounded-[6px] border border-danger/40 bg-danger-soft px-3 py-2 text-xs text-danger-fg">
          {error}
        </p>
      )}
      <Button type="submit" disabled={loading} className="w-full" size="lg">
        {loading ? "Entrando…" : "Entrar"}
      </Button>

      <div className="rounded-[10px] border border-line bg-surface-sunken/60 p-3 text-xs">
        <p className="mb-2 font-medium text-ink-muted">Cuentas demo</p>
        <div className="grid gap-1.5">
          <DemoRow
            label="Admin"
            email="admin@despachodemo.co"
            pw="DemoAdmin2026!"
            onUse={useDemo}
          />
          <DemoRow
            label="Contador"
            email="contador@despachodemo.co"
            pw="DemoConta2026!"
            onUse={useDemo}
          />
          <DemoRow
            label="Cliente"
            email="andina@clientedemo.co"
            pw="DemoAndi2026!"
            onUse={useDemo}
          />
        </div>
      </div>
    </form>
  );
}

function DemoRow({
  label,
  email,
  pw,
  onUse,
}: {
  label: string;
  email: string;
  pw: string;
  onUse: (e: string, p: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onUse(email, pw)}
      className="flex items-center justify-between gap-3 rounded-[6px] px-2 py-1 text-left hover:bg-surface-card"
    >
      <span className="font-medium text-ink">{label}</span>
      <span className="truncate font-mono text-2xs text-ink-subtle">{email}</span>
    </button>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      {/* Left panel — brand */}
      <aside className="relative hidden overflow-hidden bg-brand-700 lg:flex lg:flex-col lg:justify-between lg:p-10 lg:text-white">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(1200px 500px at 20% -10%, hsl(239 90% 66% / 0.6), transparent 70%), radial-gradient(700px 500px at 90% 110%, hsl(158 60% 40% / 0.35), transparent 60%)",
          }}
        />
        <div className="relative">
          <BrandMark className="text-white [&_p]:text-white [&_p:last-child]:text-white/70" />
        </div>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Un despacho que se opera solo.
          </h2>
          <p className="mt-3 text-sm text-white/80">
            Ingesta por WhatsApp, extracción con IA, conciliación bancaria y reportes DIAN
            en un solo lugar. Menos trabajo mecánico, más tiempo para asesorar.
          </p>
          <ul className="mt-6 space-y-3 text-sm">
            <Feature icon={<MessageSquareText className="h-4 w-4" />}>
              Recibe facturas por WhatsApp o correo y clasifícalas automáticamente.
            </Feature>
            <Feature icon={<ScanLine className="h-4 w-4" />}>
              Concilia el extracto bancario contra facturas con IA en segundos.
            </Feature>
            <Feature icon={<FileBarChart2 className="h-4 w-4" />}>
              Genera reportes mensuales y Formulario 300 IVA listos para presentar.
            </Feature>
          </ul>
        </div>
        <p className="relative text-2xs text-white/60">
          Demo pública · datos sintéticos · no conectada a la DIAN real.
        </p>
      </aside>

      {/* Right — form */}
      <section className="flex items-center justify-center px-6 py-12 lg:px-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden">
            <BrandMark />
          </div>
          <div className="mt-8 lg:mt-0">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Iniciar sesión</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Accede a tu panel con tu correo del despacho.
            </p>
          </div>
          <div className="mt-8">
            <Suspense
              fallback={
                <p className="text-sm text-ink-subtle">Cargando…</p>
              }
            >
              <LoginForm />
            </Suspense>
          </div>
        </div>
      </section>
    </main>
  );
}

function Feature({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/15 text-white">
        {icon}
      </span>
      <span className="text-white/90">{children}</span>
    </li>
  );
}
