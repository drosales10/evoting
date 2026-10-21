"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StatuteDocument } from "@/components/statute/StatuteDocument";
import { clientApiBase } from "@/lib/api-origin";
import type { StatuteArticleResult, StatuteTitleNode } from "@/lib/statute";

type DocumentPayload = {
  id: string;
  title: string;
  status: string;
  approval_threshold_pct: string;
  titles: StatuteTitleNode[];
};

type ResultsPayload = {
  quorum_met: boolean;
  ballot_count: number;
  verification: { artifact_sha256_matches: boolean; signature_valid: boolean };
  artifact: { articles?: StatuteArticleResult[] };
};

const apiUrl = clientApiBase();

export default function ClienteEstatutoDetailPage() {
  const params = useParams<{ consultationId: string }>();
  const consultationId = params.consultationId;
  const [document, setDocument] = useState<DocumentPayload | null>(null);
  const [results, setResults] = useState<ResultsPayload | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!consultationId) return;
    void fetch(`${apiUrl}/api/v1/public/statutes/${consultationId}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setMissing(true);
          return;
        }
        const payload = (await response.json()) as DocumentPayload;
        setDocument(payload);
        if (payload.status === "TALLIED") {
          const resultsResponse = await fetch(
            `${apiUrl}/api/v1/public/statutes/${consultationId}/results`,
            { cache: "no-store" },
          );
          if (resultsResponse.ok) setResults((await resultsResponse.json()) as ResultsPayload);
        }
      })
      .catch(() => setMissing(true));
  }, [consultationId]);

  if (missing) {
    return <p className="text-[var(--muted)]">Esta consulta no está publicada.</p>;
  }
  if (!document) {
    return <p className="text-[var(--muted)]">Cargando el estatuto…</p>;
  }

  return (
    <div className="space-y-6 text-[var(--ink)]">
      <div className="flex flex-wrap items-end justify-between gap-3 print:block">
        <div>
          <Link href="/cliente/estatutos" className="text-sm font-semibold text-[var(--primary)] print:hidden">
            Volver
          </Link>
          <h1 className="mt-2 text-3xl font-semibold">{document.title}</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Un artículo se aprueba con al menos {document.approval_threshold_pct}% de las boletas.
          </p>
          {results ? (
            <p className="mt-1 text-sm">
              {results.ballot_count} boletas · quórum {results.quorum_met ? "alcanzado" : "no alcanzado"} · firma{" "}
              {results.verification.signature_valid ? "válida" : "no verificada"}
            </p>
          ) : (
            <p className="mt-1 text-sm text-[var(--muted)]">
              Las respuestas de los miembros se publican con el acta.
            </p>
          )}
        </div>
        <button type="button" className="btn btn-secondary text-[var(--ink)] print:hidden" onClick={() => window.print()}>
          Imprimir
        </button>
      </div>
      <StatuteDocument titles={document.titles} results={results?.artifact.articles} />
    </div>
  );
}
