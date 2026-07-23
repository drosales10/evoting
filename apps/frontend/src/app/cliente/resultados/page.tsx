import Link from "next/link";

import { CeremonyLiveBanner } from "@/components/ceremony/CeremonyLiveBanner";
import { getPublicElections } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ClienteResultadosPage() {
  const elections = await getPublicElections().catch(() => []);
  const tallied = elections.filter((e) => e.status === "TALLIED");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Resultados oficiales</h1>
        <p className="mt-1 text-[var(--muted)]">
          Solo se listan elecciones con tally publicado, quórum cumplido y sin override de piloto.
        </p>
      </div>

      <CeremonyLiveBanner compact />

      <div className="space-y-3">
        {tallied.length === 0 ? (
          <p className="card-panel text-sm text-[var(--muted)]">Aún no hay resultados oficiales.</p>
        ) : (
          tallied.map((election) => (
            <div
              key={election.id}
              className="card-panel flex flex-wrap items-center justify-between gap-3"
            >
              <div>
                <p className="font-semibold">{election.title}</p>
                {election.broadcast_status ? (
                  <p className="text-xs text-[var(--muted)]">
                    Ceremonia: {election.has_live ? "en vivo" : election.broadcast_status}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {election.broadcast_status ? (
                  <Link
                    className="btn btn-secondary"
                    href={`/cliente/ceremonia?election=${election.id}`}
                  >
                    Ceremonia
                  </Link>
                ) : null}
                <Link
                  className="btn btn-secondary"
                  href={`/cliente/resultados/${election.id}`}
                >
                  Ver detalle
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
