"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { FeatureCollection } from "geojson";

import { CeremonyDrawer } from "@/components/ceremony/CeremonyDrawer";

const ClientMapView = dynamic(
  () => import("@/components/client/geovisor/ClientMapView").then((m) => m.ClientMapView),
  { ssr: false, loading: () => <p className="text-[var(--muted)]">Cargando geovisor…</p> },
);

type Election = {
  id: string;
  title: string;
  status: string;
  has_live?: boolean;
  broadcast_status?: string | null;
};

function mergeCollections(
  territory: FeatureCollection | null,
  results: FeatureCollection | null,
): FeatureCollection | null {
  if (!territory && !results) return null;
  if (!results) return territory;
  if (!territory) return results;

  const byKey = new Map<string, GeoJSON.Feature>();
  for (const feature of territory.features) {
    const key = `${String(feature.properties?.level)}:${String(feature.properties?.id)}`;
    byKey.set(key, feature);
  }
  for (const feature of results.features) {
    const key = `${String(feature.properties?.level)}:${String(feature.properties?.id)}`;
    const base = byKey.get(key);
    byKey.set(key, {
      ...feature,
      geometry: feature.geometry ?? base?.geometry ?? null,
      properties: { ...(base?.properties ?? {}), ...(feature.properties ?? {}) },
    });
  }
  return { type: "FeatureCollection", features: Array.from(byKey.values()) };
}

export function ClienteGeovisorClient({
  mapboxToken,
  apiUrl,
}: {
  mapboxToken: string;
  apiUrl: string;
}) {
  const [elections, setElections] = useState<Election[]>([]);
  const [electionId, setElectionId] = useState("");
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl}/api/v1/public/elections`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) return;
        const list = (await r.json()) as Election[];
        setElections(list);
        const preferred =
          list.find((e) => e.has_live) ??
          list.find((e) => e.broadcast_status === "SCHEDULED" || e.broadcast_status === "ENDED") ??
          list.find((e) => e.status === "TALLIED") ??
          list.find((e) => e.status === "ACTIVE") ??
          list.find((e) => e.status === "CLOSED") ??
          list[0];
        if (preferred) setElectionId(preferred.id);
      })
      .catch(() => undefined);
  }, [apiUrl]);

  useEffect(() => {
    if (!electionId) return;
    let cancelled = false;
    void (async () => {
      try {
        const [territoryRes, resultsRes] = await Promise.all([
          fetch(`${apiUrl}/api/v1/public/geo/territory/${electionId}?levels=N1,N2,N3,N4,N5`, {
            cache: "no-store",
          }),
          fetch(`${apiUrl}/api/v1/public/geo/results/${electionId}`, { cache: "no-store" }),
        ]);
        if (cancelled) return;

        const territory = territoryRes.ok
          ? ((await territoryRes.json()) as FeatureCollection)
          : null;
        const results = resultsRes.ok
          ? ((await resultsRes.json()) as FeatureCollection)
          : null;

        if (!territory && !results) {
          setGeojson(null);
          setError("Sin capas territoriales para esta elección.");
          setInfo(null);
          return;
        }

        setGeojson(mergeCollections(territory, results));
        setError(null);
        setInfo(
          results
            ? "Mostrando territorio + participación oficial."
            : "Mostrando territorio base (aún no hay tally oficial con quórum).",
        );
      } catch {
        if (!cancelled) {
          setError("No se pudo contactar la API pública.");
          setGeojson(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, electionId]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Geovisor de resultados</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Capas N1–N5 (DeckGL + Mapbox). Usa el botón <strong>Ceremonia</strong> para ver el live
          de YouTube del escrutinio.
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
              {e.title} ({e.status}
              {e.has_live ? " · EN VIVO" : e.broadcast_status ? " · Ceremonia" : ""})
            </option>
          ))}
        </select>
        <Link className="btn btn-secondary" href="/cliente/ceremonia">
          Página Ceremonia
        </Link>
        <Link className="btn btn-secondary" href="/cliente/resultados">
          Ver listado
        </Link>
        {electionId ? <CeremonyDrawer electionId={electionId} /> : null}
      </div>
      {error ? <p className="text-sm text-amber-400">{error}</p> : null}
      {info ? <p className="text-sm text-[var(--muted)]">{info}</p> : null}
      <div className="h-[560px] overflow-hidden rounded-2xl border border-[var(--line)]">
        <ClientMapView data={geojson} mapboxToken={mapboxToken} />
      </div>
    </div>
  );
}
