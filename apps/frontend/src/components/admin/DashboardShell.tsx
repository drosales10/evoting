"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/uiStore";

export type AdminNavItem = {
  href: string;
  label: string;
};

const DEFAULT_NAV: AdminNavItem[] = [
  { href: "/admin", label: "Resumen" },
  { href: "/admin/padron", label: "Padrón" },
  { href: "/admin/territory", label: "Territorio" },
  { href: "/admin/elections", label: "Elecciones" },
  { href: "/admin/geovisor", label: "Geovisor" },
  { href: "/admin/audit", label: "Auditoría" },
];

export function DashboardShell({
  children,
  nav = DEFAULT_NAV,
}: {
  children: React.ReactNode;
  nav?: AdminNavItem[];
}) {
  const pathname = usePathname();
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  return (
    <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
            Comisión electoral
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-[var(--ink)] md:text-3xl">
            Backoffice eVoting
          </h1>
        </div>
        <button type="button" className="btn btn-secondary" onClick={toggleSidebar}>
          {sidebarOpen ? <ChevronLeft className="mr-1 size-4" /> : <ChevronRight className="mr-1 size-4" />}
          {sidebarOpen ? "Ocultar menú" : "Mostrar menú"}
        </button>
      </div>

      <div
        className={cn(
          "grid grid-cols-1 gap-4",
          sidebarOpen ? "md:grid-cols-[240px_1fr]" : "md:grid-cols-1",
        )}
      >
        {sidebarOpen ? (
          <aside className="card-panel h-fit p-3">
            <nav className="flex flex-col gap-1" aria-label="Navegación administrativa">
              {nav.map((item) => {
                const active =
                  item.href === "/admin"
                    ? pathname === "/admin"
                    : pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-lg px-3 py-2 text-sm font-semibold transition",
                      active
                        ? "bg-[var(--accent)] text-[var(--primary-dark)]"
                        : "text-[var(--muted)] hover:bg-[var(--accent)]/50 hover:text-[var(--ink)]",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <Link
                href="/admin/login"
                className="mt-3 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--primary)]"
              >
                Sesión / MFA
              </Link>
            </nav>
          </aside>
        ) : null}

        <section className="card-panel min-h-[60vh]">{children}</section>
      </div>
    </div>
  );
}
