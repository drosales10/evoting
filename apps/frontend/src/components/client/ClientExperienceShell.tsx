"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const CLIENT_NAV = [
  { href: "/cliente", label: "Inicio" },
  { href: "/cliente/elecciones", label: "Elecciones" },
  { href: "/cliente/ceremonia", label: "Ceremonia" },
  { href: "/cliente/resultados", label: "Resultados" },
  { href: "/cliente/geovisor", label: "Geovisor" },
  { href: "/vote/login", label: "Votar" },
];

export function ClientExperienceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [dark, setDark] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    return () => {
      document.documentElement.classList.remove("dark");
    };
  }, [dark]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--background)] text-[var(--ink)]">
      <div
        aria-hidden
        className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-[var(--primary)]/20 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 bottom-10 h-80 w-80 rounded-full bg-emerald-400/10 blur-3xl"
      />

      <header className="relative z-10 border-b border-[var(--line)]/80 bg-[var(--surface)]/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-4 md:px-6">
          <Link href="/cliente" className="brand text-xl font-bold tracking-tight">
            e<span className="text-[var(--primary)]">Voting</span> Cliente
          </Link>
          <nav className="flex flex-wrap items-center gap-1 md:gap-2" aria-label="Navegación cliente">
            {CLIENT_NAV.map((item) => {
              const active =
                item.href === "/cliente"
                  ? pathname === "/cliente"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-full px-3 py-1.5 text-sm font-semibold transition",
                    active
                      ? "bg-[var(--primary)] text-[var(--background)]"
                      : "text-[var(--muted)] hover:text-[var(--ink)]",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
            <button
              type="button"
              className="btn btn-secondary ml-1 px-3 py-1.5"
              onClick={() => setDark((v) => !v)}
              aria-label="Alternar modo oscuro"
            >
              {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          </nav>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-7xl px-4 py-8 md:px-6">{children}</main>
    </div>
  );
}
