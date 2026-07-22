import Link from "next/link";

import { getPublicElectionResult } from "@/lib/api";

export const dynamic = "force-dynamic";

type ResultsPageProps = {
  params: Promise<{ electionId: string }>;
};

export default async function ElectionResultsPage({ params }: ResultsPageProps) {
  const { electionId } = await params;
  const result = await getPublicElectionResult(electionId);

  if (!result) {
    return (
      <div className="page-shell narrow-shell">
        <span className="eyebrow">Verificación pública</span>
        <h1>Resultados no disponibles</h1>
        <p className="lead">
          No existe un resultado oficial publicado para esta elección. Los tallies de piloto sin
          quórum no se muestran en el portal público.
        </p>
        <Link className="button button-secondary inline-button" href="/elections">
          Volver a elecciones
        </Link>
      </div>
    );
  }

  return (
    <div className="page-shell narrow-shell">
      <span className="eyebrow">Resultado oficial</span>
      <h1>{result.title}</h1>
      <p className="lead">
        Resultado agregado publicado después de verificar el artefacto firmado, la integridad de las
        boletas y el quórum electoral.
      </p>
      <section className="empty-state" aria-labelledby="result-summary-title">
        <h2 id="result-summary-title">Escrutinio</h2>
        <p>Boletas válidas contabilizadas: {result.ballot_count}</p>
        <div className="election-list">
          {result.counts.map((count) => (
            <article className="election-item" key={count.slate_id}>
              <div>
                <h3>{count.slate_name}</h3>
                <p>{count.votes} votos</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="empty-state" aria-labelledby="verification-title">
        <h2 id="verification-title">Verificación de integridad</h2>
        <p>
          La API pública recalculó la huella SHA-256 y verificó la firma RSA-PSS con la clave pública
          de la elección antes de entregar este resultado.
        </p>
        <p>
          Estado de verificación: {result.verification.signature_valid && result.verification.artifact_sha256_matches
            ? "válido"
            : "no válido"}
        </p>
        <p>
          Huella SHA-256 del artefacto firmado:
          <br />
          <code>{result.artifact_sha256}</code>
        </p>
        <p>
          Huella SHA-256 de la clave pública electoral:
          <br />
          <code>{result.public_key_sha256}</code>
        </p>
        <p>Publicado: {new Date(result.published_at).toLocaleString("es-ES")}</p>
        <details>
          <summary>Mostrar artefacto firmado para verificación independiente</summary>
          <p>
            El artefacto contiene únicamente metadatos agregados, conteos y huellas de recibos; no
            contiene claves privadas, identidades ni boletas descifradas.
          </p>
          <pre>{JSON.stringify(result.artifact, null, 2)}</pre>
          <p>Firma RSA-PSS:</p>
          <code>{result.signature}</code>
          <p>Clave pública RSA:</p>
          <pre>{result.public_key}</pre>
        </details>
      </section>
      <Link className="button button-secondary inline-button" href="/elections">
        Volver a elecciones
      </Link>
    </div>
  );
}
