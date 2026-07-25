"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type MemberTypeCount = {
  member_type: string;
  count: number;
};

type Overview = {
  organization_name: string;
  organization_slug: string;
  roles: string[];
  member_count: number;
  active_member_count: number;
  inactive_member_count: number;
  member_type_counts: MemberTypeCount[];
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

        <div>
          <p className="eyebrow mb-2">Padrón · Estatus</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="card-panel">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Total</p>
              <p className="mt-2 text-3xl font-semibold">{overview?.member_count ?? "—"}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">Miembros registrados</p>
            </div>
            <div className="card-panel">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                Estatus activos
              </p>
              <p className="mt-2 text-3xl font-semibold text-emerald-700 dark:text-emerald-300">
                {overview?.active_member_count ?? "—"}
              </p>
              <p className="mt-1 text-sm text-[var(--muted)]">Columna Estatus = Activo</p>
            </div>
            <div className="card-panel">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                Estatus inactivos
              </p>
              <p className="mt-2 text-3xl font-semibold text-amber-700 dark:text-amber-300">
                {overview?.inactive_member_count ?? "—"}
              </p>
              <p className="mt-1 text-sm text-[var(--muted)]">Columna Estatus = Inactivo</p>
            </div>
          </div>
        </div>

        <div>
          <p className="eyebrow mb-2">Padrón · Tipo</p>
          <p className="mb-2 text-sm text-[var(--muted)]">
            Categoría de membresía (voz/voto). Distinta del estatus operativo.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(overview?.member_type_counts ?? []).map((item) => (
              <div className="card-panel" key={item.member_type}>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                  {item.member_type}
                </p>
                <p className="mt-2 text-3xl font-semibold">{item.count}</p>
              </div>
            ))}
            {!overview ? (
              <div className="card-panel">
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Tipo</p>
                <p className="mt-2 text-3xl font-semibold">—</p>
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
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
