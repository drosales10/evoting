import Link from "next/link";

import { CeremonyPublicSection } from "@/components/ceremony/CeremonyPublicSection";
import { ResultsDashboard } from "@/components/results/ResultsDashboard";
import { getPublicElectionResult } from "@/lib/api";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ electionId: string }>;
};

export default async function ClienteResultadoDetallePage({ params }: PageProps) {
  const { electionId } = await params;
  const result = await getPublicElectionResult(electionId);
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

  if (!result) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Resultados no disponibles</h1>
        <p className="text-[var(--muted)]">
          No hay un resultado oficial publicado para esta elección (o el tally es de piloto sin
          quórum). Puedes seguir la ceremonia si está anunciada.
        </p>
        <CeremonyPublicSection electionId={electionId} />
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-secondary" href="/cliente/resultados">
            Volver
          </Link>
          <Link className="btn btn-primary" href="/cliente/geovisor">
            Geovisor
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
          Resultado oficial
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{result.title}</h1>
        <p className="mt-2 text-[var(--muted)]">
          Tablero de participación, plancha ganadora y mapa espacial.
        </p>
      </div>

      <ResultsDashboard
        result={result}
        mapMode="public"
        geovisorHref="/cliente/geovisor"
        backHref="/cliente/resultados"
        verifyHref={`/verify/${result.artifact_sha256}`}
        mapboxToken={mapboxToken}
        afterVerification={<CeremonyPublicSection electionId={electionId} />}
      />
    </div>
  );
}
