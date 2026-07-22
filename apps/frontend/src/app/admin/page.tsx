"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Overview = {
  organization_name: string;
  organization_slug: string;
  roles: string[];
  member_count: number;
  election_count: number;
  encrypted_ballot_count: number;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AdminHomePage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl()}/api/v1/admin/overview`, { credentials: "include", cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as Overview & { detail?: string };
        if (!response.ok) {
          setError(
            response.status === 401
              ? "Sesión administrativa inactiva. Accede en /admin/login."
              : payload.detail ?? "No se pudo cargar el resumen.",
          );
          return;
        }
        setOverview(payload);
      })
      .catch(() => setError("No se pudo contactar la API administrativa."));
  }, []);

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Resumen de comisión</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Padrón, territorio, elecciones y geovisor viven en pantallas propias.
          </p>
        </div>

        {error ? <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm">{error}</p> : null}

        {overview ? (
          <div className="notice">
            <strong>{overview.organization_name}</strong>
            <p>Organización: {overview.organization_slug}</p>
            <p>Roles: {overview.roles.join(", ")}</p>
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card-panel">
            <p className="eyebrow">Padrón</p>
            <p className="mt-2 text-3xl font-semibold">{overview?.member_count ?? "—"}</p>
          </div>
          <div className="card-panel">
            <p className="eyebrow">Elecciones</p>
            <p className="mt-2 text-3xl font-semibold">{overview?.election_count ?? "—"}</p>
          </div>
          <div className="card-panel">
            <p className="eyebrow">Urna</p>
            <p className="mt-2 text-3xl font-semibold">{overview?.encrypted_ballot_count ?? "—"}</p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { href: "/admin/padron", label: "Padrón", desc: "Miembros e importación" },
            { href: "/admin/territory", label: "Territorio", desc: "N2–N5" },
            { href: "/admin/elections", label: "Elecciones", desc: "Alcance y ciclo" },
            { href: "/admin/geovisor", label: "Geovisor", desc: "Leaflet N1–N5" },
          ].map((card) => (
            <Link key={card.href} href={card.href} className="card-panel transition hover:border-[var(--primary)]">
              <p className="font-semibold">{card.label}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">{card.desc}</p>
            </Link>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
