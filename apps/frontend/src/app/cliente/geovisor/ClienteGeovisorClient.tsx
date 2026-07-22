"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

const ClientMapView = dynamic(
  () => import("@/components/client/geovisor/ClientMapView").then((m) => m.ClientMapView),
  { ssr: false, loading: () => <p className="text-[var(--muted)]">Cargando geovisor…</p> },
);

type Election = { id: string; title: string; status: string };

export function ClienteGeovisorClient({
  mapboxToken,
  apiUrl,
}: {
  mapboxToken: string;
  apiUrl: string;
}) {
  const [elections, setElections] = useState<Election[]>([]);
  const [electionId, setElectionId] = useState("");
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl}/api/v1/public/elections`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) return;
        const list = (await r.json()) as Election[];
        setElections(list);
        const tallied = list.find((e) => e.status === "TALLIED");
        if (tallied) setElectionId(tallied.id);
      })
      .catch(() => undefined);
  }, [apiUrl]);

  useEffect(() => {
    if (!electionId) return;
    void fetch(`${apiUrl}/api/v1/public/geo/results/${electionId}`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) {
          setError("Sin resultados geo oficiales para esta elección.");
          setGeojson(null);
          return;
        }
        setGeojson((await r.json()) as GeoJSON.FeatureCollection);
        setError(null);
      })
      .catch(() => setError("No se pudo contactar la API pública."));
  }, [apiUrl, electionId]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Geovisor de resultados</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Visualización DeckGL + Mapbox de participación por región (N2) y estado (N3). Solo tallies
          oficiales con quórum.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input-field max-w-md"
          value={electionId}
          onChange={(e) => setElectionId(e.target.value)}
        >
          <option value="">Selecciona elección</option>
          {elections.map((e) => (
            <option key={e.id} value={e.id}>
              {e.title} ({e.status})
            </option>
          ))}
        </select>
        <Link className="btn btn-secondary" href="/cliente/resultados">
          Ver listado
        </Link>
      </div>
      {error ? <p className="text-sm text-amber-400">{error}</p> : null}
      <div className="h-[560px] overflow-hidden rounded-2xl border border-[var(--line)]">
        <ClientMapView data={geojson} mapboxToken={mapboxToken} />
      </div>
    </div>
  );
}
