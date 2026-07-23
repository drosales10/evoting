import Link from "next/link";

import { CeremonyPublicSection } from "@/components/ceremony/CeremonyPublicSection";
import { getPublicElectionResult } from "@/lib/api";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ electionId: string }>;
};

export default async function ClienteResultadoDetallePage({ params }: PageProps) {
  const { electionId } = await params;
  const result = await getPublicElectionResult(electionId);

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
          Escrutinio agregado verificado. Boletas válidas: {result.ballot_count}.
        </p>
      </div>

      <CeremonyPublicSection electionId={electionId} />

      <section className="card-panel space-y-3">
        <h2 className="text-lg font-semibold">Conteos por plancha</h2>
        <ul className="space-y-2">
          {result.counts.map((count) => (
            <li
              key={count.slate_id}
              className="flex items-center justify-between border-b border-[var(--line)] py-2 text-sm"
            >
              <span className="font-semibold">{count.slate_name}</span>
              <span>{count.votes} votos</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card-panel space-y-2 text-sm">
        <h2 className="text-lg font-semibold">Verificación</h2>
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
          Publicado: {new Date(result.published_at).toLocaleString("es-ES")}
        </p>
        <details className="pt-2">
          <summary className="cursor-pointer font-semibold">Artefacto firmado</summary>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs">
            {JSON.stringify(result.artifact, null, 2)}
          </pre>
        </details>
      </section>

      <div className="flex flex-wrap gap-2">
        <Link className="btn btn-secondary" href="/cliente/resultados">
          Volver al listado
        </Link>
        <Link className="btn btn-primary" href="/cliente/geovisor">
          Ver en geovisor
        </Link>
        <Link className="btn btn-secondary" href={`/verify/${result.artifact_sha256}`}>
          Verificar huella
        </Link>
      </div>
    </div>
  );
}
