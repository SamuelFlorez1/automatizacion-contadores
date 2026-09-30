import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Despacho — automatización contable",
  description: "Ingesta, conciliación, reportes y agente WhatsApp para despachos contables.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-screen bg-surface text-ink antialiased">
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            classNames: {
              toast: "border border-line bg-surface-card text-ink shadow-pop",
              description: "text-ink-muted",
              success: "!border-success/40",
              error: "!border-danger/40",
            },
          }}
        />
      </body>
    </html>
  );
}
