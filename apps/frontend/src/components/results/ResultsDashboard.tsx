"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { PublicElectionResult } from "@evoting/shared";

import { ResultsParticipationMap } from "@/components/results/ResultsParticipationMap";
import { summarizeElectionResult } from "@/components/results/summarizeElectionResult";
import { formatAppDateTime } from "@/lib/datetime";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ResultsDashboard({
  result,
  mapMode = "public",
  geovisorHref,
  backHref,
  verifyHref,
  mapboxToken,
  showVerification = true,
  afterVerification,
}: {
  result: PublicElectionResult;
  mapMode?: "public" | "admin";
  geovisorHref: string;
  backHref?: string;
  verifyHref?: string;
  mapboxToken?: string;
  showVerification?: boolean;
  afterVerification?: ReactNode;
}) {
  const summary = summarizeElectionResult(result);
  const base = apiUrl();
  const territoryUrl =
    mapMode === "admin"
      ? `${base}/api/v1/admin/geo/features?levels=N1,N2,N3,N4,N5`
      : `${base}/api/v1/public/geo/territory/${result.election_id}?levels=N1,N2,N3,N4,N5`;
  const resultsUrl =
    mapMode === "admin"
      ? `${base}/api/v1/admin/geo/results/${result.election_id}`
      : `${base}/api/v1/public/geo/results/${result.election_id}`;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="KPIs de participación">
        <div className="card-panel">
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Elegibles</p>
          <p className="mt-2 text-3xl font-semibold">{summary.eligible}</p>
        </div>
        <div className="card-panel">
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Votaron</p>
          <p className="mt-2 text-3xl font-semibold text-emerald-700 dark:text-emerald-300">
            {summary.voted}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">{summary.participation_pct}% participación</p>
        </div>
        <div className="card-panel">
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Boletas</p>
          <p className="mt-2 text-3xl font-semibold">{summary.ballots}</p>
        </div>
        <div className="card-panel">
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">Quórum</p>
          <p className="mt-2 text-3xl font-semibold">
            {summary.quorum_met ? (
              <span className="text-emerald-700 dark:text-emerald-300">Cumplido</span>
            ) : (
              <span className="text-amber-700 dark:text-amber-300">No</span>
            )}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Requerido {summary.quorum_required} ({summary.quorum_threshold_pct}%)
          </p>
        </div>
      </div>

      <section className="card-panel space-y-3" aria-labelledby="winner-title">
        <p className="eyebrow">Plancha ganadora</p>
        <h2 id="winner-title" className="text-xl font-semibold">
          {summary.is_tie
            ? "Empate en el primer lugar"
            : summary.winner
              ? summary.winner.slate_name
              : "Sin votos registrados"}
        </h2>
        {summary.winner ? (
          <p className="text-[var(--muted)]">
            {summary.winner.votes} votos · {summary.winner.vote_pct}%
            {summary.standings[1]
              ? ` · Margen: ${summary.winner.votes - summary.standings[1].votes} sobre ${summary.standings[1].slate_name}`
              : null}
          </p>
        ) : summary.is_tie ? (
          <p className="text-[var(--muted)]">
            {summary.standings
              .filter((row) => row.is_tie)
              .map((row) => `${row.slate_name} (${row.votes})`)
              .join(" · ")}
          </p>
        ) : null}
      </section>

      <section className="card-panel space-y-4" aria-labelledby="ranking-title">
        <h2 id="ranking-title" className="text-lg font-semibold">
          Ranking de planchas
        </h2>
        <ul className="space-y-3">
          {summary.standings.map((row) => (
            <li key={row.slate_id} className="space-y-1">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-semibold">
                  #{row.rank} {row.slate_name}
                  {row.is_winner ? (
                    <span className="ml-2 text-xs font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                      Ganadora
                    </span>
                  ) : null}
                  {row.is_tie ? (
                    <span className="ml-2 text-xs font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                      Empate
                    </span>
                  ) : null}
                </span>
                <span className="text-[var(--muted)]">
                  {row.votes} votos · {row.vote_pct}%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--accent)]/40">
                <div
                  className="h-full rounded-full bg-[var(--primary)]"
                  style={{ width: `${Math.min(100, row.vote_pct)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card-panel space-y-3" aria-labelledby="map-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Participación espacial</p>
            <h2 id="map-title" className="text-lg font-semibold">
              Mapa N1–N5
            </h2>
          </div>
          <Link className="btn btn-secondary" href={geovisorHref}>
            Abrir geovisor
          </Link>
        </div>
        <ResultsParticipationMap
          electionId={result.election_id}
          territoryUrl={territoryUrl}
          resultsUrl={resultsUrl}
          credentials={mapMode === "admin" ? "include" : "omit"}
          mapboxToken={mapboxToken}
        />
      </section>

      {showVerification ? (
        <section className="card-panel space-y-2 text-sm" aria-labelledby="verify-title">
          <h2 id="verify-title" className="text-lg font-semibold">
            Verificación
          </h2>
          <p>
            Estado:{" "}
            {result.verification.signature_valid && result.verification.artifact_sha256_matches
              ? "válido"
              : "no válido"}
          </p>
          <p className="break-all text-[var(--muted)]">
            SHA-256 artefacto: <code>{result.artifact_sha256}</code>
          </p>
          <p className="text-[var(--muted)]">
            Publicado: {formatAppDateTime(result.published_at)}
          </p>
          <details className="pt-2">
            <summary className="cursor-pointer font-semibold">Artefacto firmado</summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs dark:bg-black/50">
              {JSON.stringify(result.artifact, null, 2)}
            </pre>
          </details>
        </section>
      ) : null}

      {afterVerification}

      <div className="flex flex-wrap gap-2">
        {backHref ? (
          <Link className="btn btn-secondary" href={backHref}>
            Volver al listado
          </Link>
        ) : null}
        <Link className="btn btn-primary" href={geovisorHref}>
          Ver en geovisor
        </Link>
        {verifyHref ? (
          <Link className="btn btn-secondary" href={verifyHref}>
            Verificar huella
          </Link>
        ) : null}
      </div>
    </div>
  );
}
