"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

type VerifyPayload = {
  artifact_hash: string;
  election_id: string;
  title: string;
  verification: {
    artifact_sha256_matches: boolean;
    signature_valid: boolean;
  };
  ballot_count: number;
  quorum_met: boolean;
  counts: Array<{ slate_id: string; slate_name: string; votes: number }>;
  download_path: string;
  detail?: string;
};

export default function VerifyArtifactPage() {
  const params = useParams<{ artifactHash: string }>();
  const [data, setData] = useState<VerifyPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = params.artifactHash;
    if (!hash) return;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    void fetch(`${apiUrl}/api/v1/public/verify/${hash}`, { cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as VerifyPayload;
        if (!response.ok) {
          setError(payload.detail ?? "No se pudo verificar el artefacto.");
          return;
        }
        setData(payload);
      })
      .catch(() => setError("No se pudo contactar la API pública."));
  }, [params.artifactHash]);

  return (
    <main className="empty-state">
      <span className="eyebrow">Verificación pública</span>
      <h1>Verificar artefacto de escrutinio</h1>
      <p>
        Comprueba huella SHA-256, firma RSA-PSS y conteos agregados sin depender únicamente de la
        interfaz de resultados.
      </p>
      {error ? <p className="form-message" role="alert">{error}</p> : null}
      {data ? (
        <>
          <p className="form-message">
            {data.title} · {data.artifact_hash.slice(0, 16)}…
          </p>
          <ul>
            <li>SHA-256 coincide: {data.verification.artifact_sha256_matches ? "sí" : "no"}</li>
            <li>Firma válida: {data.verification.signature_valid ? "sí" : "no"}</li>
            <li>Quórum: {data.quorum_met ? "cumplido" : "no"}</li>
            <li>Boletas: {data.ballot_count}</li>
          </ul>
          <h2>Conteos</h2>
          <ul>
            {data.counts.map((item) => (
              <li key={item.slate_id}>
                {item.slate_name}: {item.votes}
              </li>
            ))}
          </ul>
          <a
            className="button button-primary inline-button"
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${data.download_path}`}
          >
            Descargar artefacto firmado
          </a>
        </>
      ) : !error ? (
        <p className="form-message">Verificando…</p>
      ) : null}
    </main>
  );
}
