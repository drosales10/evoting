"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import type { PublicElectionResult } from "@evoting/shared";

import { DashboardShell } from "@/components/admin/DashboardShell";
import { ResultsDashboard } from "@/components/results/ResultsDashboard";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type PageProps = {
  params: Promise<{ electionId: string }>;
};

export default function AdminResultadoDetallePage({ params }: PageProps) {
  const { electionId } = use(params);
  const [result, setResult] = useState<PublicElectionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void fetch(`${apiUrl()}/api/v1/admin/elections/${electionId}/results`, {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (response) => {
        if (cancelled) return;
        if (!response.ok) {
          setResult(null);
          setError(
            response.status === 404
              ? "No hay tally publicado para esta elección."
              : response.status === 403
                ? "Tu rol no puede consultar resultados. Se requiere SUPER_ADMIN o ELECTORAL_JUSTICE."
                : `No se pudieron cargar los resultados (${response.status}).`,
          );
          return;
        }
        setResult((await response.json()) as PublicElectionResult);
        setError(null);
      })
      .catch(() => {
        if (!cancelled) setError("Error de red al cargar resultados.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [electionId]);

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <p className="eyebrow">Comisión · Resultados</p>
          <h2 className="mt-1 text-xl font-semibold">
            {result?.title ?? (loading ? "Cargando…" : "Resultados")}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Dashboard interno (incluye escrutinios piloto).
          </p>
        </div>

        {error ? (
          <div className="card-panel space-y-3">
            <p className="text-sm text-red-600 dark:text-amber-300">{error}</p>
            <Link className="btn btn-secondary" href="/admin/resultados">
              Volver
            </Link>
          </div>
        ) : null}

        {loading && !result ? (
          <p className="text-sm text-[var(--muted)]">Cargando tablero…</p>
        ) : null}

        {result ? (
          <ResultsDashboard
            result={result}
            mapMode="admin"
            geovisorHref={`/admin/geovisor?election=${result.election_id}`}
            backHref="/admin/resultados"
            verifyHref={`/verify/${result.artifact_sha256}`}
            mapboxToken={process.env.NEXT_PUBLIC_MAPBOX_TOKEN}
          />
        ) : null}
      </div>
    </DashboardShell>
  );
}
