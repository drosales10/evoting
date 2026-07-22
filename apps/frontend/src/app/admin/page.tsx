"use client";

import Link from "next/link";

import { DashboardShell } from "@/components/admin/DashboardShell";
import { AdminOverview } from "@/components/admin/admin-overview";

export default function AdminHomePage() {
  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Resumen de comisión</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Navega por padrón, territorio, elecciones y geovisor. La auditoría detallada sigue
            disponible por elección.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { href: "/admin/padron", label: "Padrón", desc: "Miembros e importación" },
            { href: "/admin/territory", label: "Territorio", desc: "Regiones y estados" },
            { href: "/admin/elections", label: "Elecciones", desc: "Ciclo y escrutinio" },
            { href: "/admin/geovisor", label: "Geovisor", desc: "Leaflet N1–N5" },
          ].map((card) => (
            <Link key={card.href} href={card.href} className="card-panel transition hover:border-[var(--primary)]">
              <p className="font-semibold">{card.label}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">{card.desc}</p>
            </Link>
          ))}
        </div>
        <AdminOverview />
      </div>
    </DashboardShell>
  );
}
