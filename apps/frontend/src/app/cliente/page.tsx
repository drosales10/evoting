import Link from "next/link";

import { LatestElectionResultsSection } from "@/components/results/LatestElectionResultsSection";
import { getPublicElectionResult, getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

async function getLatestOfficialResult() {
  const elections = await getPublicElections();
  const tallied = elections
    .filter((election) => election.status === "TALLIED")
    .sort((left, right) => {
      const endDelta = new Date(right.end_time).getTime() - new Date(left.end_time).getTime();
      if (endDelta !== 0) return endDelta;
      return new Date(right.start_time).getTime() - new Date(left.start_time).getTime();
    });

  for (const election of tallied) {
    const result = await getPublicElectionResult(election.id);
    if (result) return result;
  }
  return null;
}

export default async function ClienteHomePage() {
  const latestResult = await getLatestOfficialResult();

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-8 md:p-12">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--primary)]">
          Área cliente
        </p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight md:text-5xl">
          Resultados, territorio y ceremonia de escrutinio
        </h1>
        <p className="mt-4 max-w-2xl text-[var(--muted)]">
          Consulta el resultado oficial más reciente, explora la participación en el geovisor y
          sigue la ceremonia de escrutinio cuando esté anunciada.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            className="btn btn-primary"
            href={
              latestResult
                ? `/cliente/resultados/${latestResult.election_id}`
                : "/cliente/resultados"
            }
          >
            Ver resultados
          </Link>
          <Link className="btn btn-secondary" href="/cliente/geovisor">
            Abrir geovisor
          </Link>
          <Link className="btn btn-secondary" href="/cliente/elecciones">
            Ver elecciones
          </Link>
          <Link className="btn btn-secondary" href="/cliente/ceremonia">
            Ceremonia
          </Link>
          <Link className="btn btn-secondary" href="/vote/login">
            Emitir voto
          </Link>
        </div>
      </section>

      {latestResult ? (
        <LatestElectionResultsSection result={latestResult} />
      ) : (
        <section className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--surface)] p-5">
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
            Resultados oficiales
          </p>
          <h2 className="mt-2 text-xl font-semibold">Aún no hay una elección escrutada</h2>
          <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
            Cuando la comisión publique el tally oficial de una elección, el resumen de la más
            reciente aparecerá aquí.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link className="btn btn-secondary" href="/cliente/resultados">
              Ir a resultados
            </Link>
            <Link className="btn btn-secondary" href="/cliente/ceremonia">
              Ver ceremonia
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
