import Link from "next/link";

import { getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ClienteEleccionesPage() {
  const elections = await getPublicElections().catch(() => []);
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Elecciones</h1>
      <p className="text-[var(--muted)]">Listado público de convocatorias disponibles.</p>
      <div className="space-y-3">
        {elections.length === 0 ? (
          <p className="card-panel text-sm text-[var(--muted)]">No hay elecciones publicadas.</p>
        ) : (
          elections.map((election) => (
            <div
              key={election.id}
              className="card-panel flex flex-wrap items-center justify-between gap-3"
            >
              <div>
                <p className="font-semibold">{election.title}</p>
                <p className="text-sm text-[var(--muted)]">{election.status}</p>
              </div>
              <div className="flex gap-2">
                {election.status === "TALLIED" ? (
                  <Link
                    className="btn btn-secondary"
                    href={`/cliente/resultados/${election.id}`}
                  >
                    Resultados
                  </Link>
                ) : null}
                <Link className="btn btn-primary" href="/cliente/geovisor">
                  Mapa
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
