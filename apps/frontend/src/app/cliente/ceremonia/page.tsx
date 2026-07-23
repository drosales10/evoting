"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import {
  CeremonyPlayer,
  statusLabel,
  type CeremonyBroadcast,
} from "@/components/ceremony/CeremonyPlayer";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ElectionSummary = {
  id: string;
  title: string;
  status: string;
  broadcast_status?: string | null;
  has_live?: boolean;
};

function CeremoniaClient() {
  const searchParams = useSearchParams();
  const requestedId = searchParams.get("election") ?? "";
  const [elections, setElections] = useState<ElectionSummary[]>([]);
  const [electionId, setElectionId] = useState(requestedId);
  const [broadcast, setBroadcast] = useState<CeremonyBroadcast | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl()}/api/v1/public/elections`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const list = (await response.json()) as ElectionSummary[];
        const withBroadcast = list.filter((e) => Boolean(e.broadcast_status));
        setElections(withBroadcast.length > 0 ? withBroadcast : list);
        const preferred =
          list.find((e) => e.id === requestedId) ??
          list.find((e) => e.has_live) ??
          list.find((e) => e.broadcast_status) ??
          list[0];
        if (preferred) setElectionId(preferred.id);
      })
      .catch(() => setError("No se pudo cargar el listado de elecciones."));
  }, [requestedId]);

  useEffect(() => {
    if (!electionId) {
      setBroadcast(null);
      return;
    }
    let cancelled = false;
    void fetch(`${apiUrl()}/api/v1/public/elections/${electionId}/broadcast`, {
      cache: "no-store",
    })
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 404) {
          setBroadcast(null);
          setError("Esta elección aún no tiene ceremonia YouTube anunciada.");
          return;
        }
        if (!response.ok) {
          setBroadcast(null);
          setError("No se pudo cargar la ceremonia.");
          return;
        }
        setBroadcast((await response.json()) as CeremonyBroadcast);
        setError(null);
      })
      .catch(() => {
        if (!cancelled) setError("Error de red al cargar la ceremonia.");
      });
    return () => {
      cancelled = true;
    };
  }, [electionId]);

  const selectedTitle = useMemo(
    () => elections.find((e) => e.id === electionId)?.title,
    [elections, electionId],
  );

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
          Evidencia pública
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Ceremonia de escrutinio</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Live de YouTube del cierre, la comparación de claves (fuera del sistema) y la
          publicación de resultados. Complementa —no sustituye— la verificación criptográfica.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[240px] flex-1 text-sm font-bold">
          Elección
          <select
            className="input-field mt-1"
            value={electionId}
            onChange={(e) => setElectionId(e.target.value)}
          >
            <option value="">Selecciona una elección</option>
            {elections.map((election) => (
              <option key={election.id} value={election.id}>
                {election.title}
                {election.has_live ? " · EN VIVO" : ""}
                {election.broadcast_status && !election.has_live
                  ? ` · ${statusLabel(election.broadcast_status)}`
                  : ""}
              </option>
            ))}
          </select>
        </label>
        <Link className="btn btn-secondary" href="/cliente/geovisor">
          Geovisor
        </Link>
        {electionId ? (
          <Link className="btn btn-secondary" href={`/cliente/resultados/${electionId}`}>
            Resultados
          </Link>
        ) : null}
      </div>

      {selectedTitle ? (
        <p className="text-sm text-[var(--muted)]">
          Elección seleccionada: <span className="font-semibold text-[var(--ink)]">{selectedTitle}</span>
        </p>
      ) : null}
      {error ? <p className="text-sm text-amber-400">{error}</p> : null}
      {broadcast ? (
        <section className="card-panel">
          <CeremonyPlayer broadcast={broadcast} />
        </section>
      ) : null}
    </div>
  );
}

export default function ClienteCeremoniaPage() {
  return (
    <Suspense fallback={<p className="text-[var(--muted)]">Cargando ceremonia…</p>}>
      <CeremoniaClient />
    </Suspense>
  );
}
