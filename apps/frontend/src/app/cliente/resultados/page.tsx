import Link from "next/link";

import { getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ClienteResultadosPage() {
  const elections = await getPublicElections().catch(() => []);
  const tallied = elections.filter((e) => e.status === "TALLIED");
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Resultados oficiales</h1>
      <p className="text-[var(--muted)]">
        Solo se listan elecciones con tally publicado, quórum cumplido y sin override de piloto.
      </p>
      <div className="space-y-3">
        {tallied.length === 0 ? (
          <p className="card-panel text-sm text-[var(--muted)]">Aún no hay resultados oficiales.</p>
        ) : (
          tallied.map((election) => (
            <div key={election.id} className="card-panel flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold">{election.title}</p>
              <div className="flex gap-2">
                <Link className="btn btn-secondary" href={`/elections/${election.id}/results`}>
                  Verificar
                </Link>
                <Link className="btn btn-primary" href="/cliente/geovisor">
                  Geovisor
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
