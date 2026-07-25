import Link from "next/link";
import type { PublicElectionResult } from "@evoting/shared";

import { summarizeElectionResult } from "@/components/results/summarizeElectionResult";
import { formatAppDateTime } from "@/lib/datetime";

export function LatestElectionResultsSection({
  result,
}: {
  result: PublicElectionResult;
}) {
  const summary = summarizeElectionResult(result);
  const topStandings = summary.standings.slice(0, 3);

  return (
    <section
      className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)]"
      aria-labelledby="latest-results-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--line)] px-5 py-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
            Última elección · Resultado oficial
          </p>
          <h2 id="latest-results-title" className="mt-1 text-xl font-semibold">
            {result.title}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Publicado {formatAppDateTime(result.published_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            className="btn btn-primary !px-3 !py-2 text-xs"
            href={`/cliente/resultados/${result.election_id}`}
          >
            Ver resultado completo
          </Link>
          <Link className="btn btn-secondary !px-3 !py-2 text-xs" href="/cliente/geovisor">
            Geovisor
          </Link>
        </div>
      </div>

      <div className="space-y-5 p-5">
        <div className="grid gap-3 sm:grid-cols-3" aria-label="Resumen de participación">
          <div className="rounded-xl border border-[var(--line)] bg-[var(--background)] px-4 py-3">
            <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              Participación
            </p>
            <p className="mt-1 text-2xl font-semibold">{summary.participation_pct}%</p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {summary.voted} de {summary.eligible} elegibles
            </p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--background)] px-4 py-3">
            <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              Boletas
            </p>
            <p className="mt-1 text-2xl font-semibold">{summary.ballots}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Quórum {summary.quorum_met ? "cumplido" : "no cumplido"}
            </p>
          </div>
          <div className="rounded-xl border border-[var(--line)] bg-[var(--background)] px-4 py-3">
            <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              Plancha ganadora
            </p>
            <p className="mt-1 text-lg font-semibold leading-snug">
              {summary.is_tie
                ? "Empate"
                : summary.winner
                  ? summary.winner.slate_name
                  : "Sin votos"}
            </p>
            {summary.winner ? (
              <p className="mt-1 text-xs text-[var(--muted)]">
                {summary.winner.votes} votos · {summary.winner.vote_pct}%
              </p>
            ) : null}
          </div>
        </div>

        {topStandings.length > 0 ? (
          <div>
            <h3 className="text-sm font-semibold">Ranking (top {topStandings.length})</h3>
            <ul className="mt-3 space-y-2">
              {topStandings.map((row) => (
                <li key={row.slate_id} className="space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-semibold">
                      #{row.rank} {row.slate_name}
                      {row.is_winner ? (
                        <span className="ml-2 text-xs font-bold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                          Ganadora
                        </span>
                      ) : null}
                    </span>
                    <span className="text-[var(--muted)]">
                      {row.votes} · {row.vote_pct}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[var(--accent)]/40">
                    <div
                      className="h-full rounded-full bg-[var(--primary)]"
                      style={{ width: `${Math.min(100, row.vote_pct)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
