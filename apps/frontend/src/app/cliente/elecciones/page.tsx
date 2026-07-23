import Link from "next/link";

import { CeremonyLiveBanner } from "@/components/ceremony/CeremonyLiveBanner";
import { getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ClienteEleccionesPage() {
  const elections = await getPublicElections().catch(() => []);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Elecciones</h1>
        <p className="mt-1 text-[var(--muted)]">
          Listado público. Si hay live de escrutinio, verás el acceso a la ceremonia.
        </p>
      </div>

      <CeremonyLiveBanner compact />

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
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-semibold">{election.title}</p>
                  {election.has_live ? (
                    <span className="rounded-full bg-red-600/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-300">
                      En vivo
                    </span>
                  ) : election.broadcast_status ? (
                    <span className="rounded-full border border-[var(--line)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]">
                      Ceremonia
                    </span>
                  ) : null}
                </div>
                <p className="text-sm text-[var(--muted)]">{election.status}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {election.broadcast_status ? (
                  <Link
                    className="btn btn-primary"
                    href={`/cliente/ceremonia?election=${election.id}`}
                  >
                    Ceremonia
                  </Link>
                ) : null}
                {election.status === "TALLIED" ? (
                  <Link
                    className="btn btn-secondary"
                    href={`/cliente/resultados/${election.id}`}
                  >
                    Resultados
                  </Link>
                ) : null}
                <Link className="btn btn-secondary" href="/cliente/geovisor">
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
