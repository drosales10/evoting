"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import type { FeatureCollection } from "geojson";

const ClientMapView = dynamic(
  () => import("@/components/client/geovisor/ClientMapView").then((m) => m.ClientMapView),
  { ssr: false, loading: () => <p className="p-4 text-sm text-[var(--muted)]">Cargando mapa…</p> },
);

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

export function ResultsParticipationMap({
  electionId,
  territoryUrl,
  resultsUrl,
  credentials = "omit",
  mapboxToken,
  heightClassName = "h-[320px]",
}: {
  electionId: string;
  territoryUrl: string;
  resultsUrl: string;
  credentials?: RequestCredentials;
  mapboxToken?: string;
  heightClassName?: string;
}) {
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [info, setInfo] = useState("Cargando participación espacial…");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [territoryRes, resultsRes] = await Promise.all([
          fetch(territoryUrl, { cache: "no-store", credentials }),
          fetch(resultsUrl, { cache: "no-store", credentials }),
        ]);
        if (cancelled) return;
        const territory = territoryRes.ok
          ? ((await territoryRes.json()) as FeatureCollection)
          : null;
        const results = resultsRes.ok
          ? ((await resultsRes.json()) as FeatureCollection)
          : null;
        setGeojson(mergeCollections(territory, results));
        setInfo(
          results
            ? "Participación territorial (votaron / elegibles / %)."
            : territory
              ? "Territorio base sin overlay de participación."
              : "Sin capas espaciales para esta elección.",
        );
      } catch {
        if (!cancelled) {
          setGeojson(null);
          setInfo("No se pudo cargar el mapa de participación.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [credentials, electionId, resultsUrl, territoryUrl]);

  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--muted)]">{info}</p>
      <div className={`overflow-hidden rounded-xl border border-[var(--line)] ${heightClassName}`}>
        <ClientMapView data={geojson} mapboxToken={mapboxToken} compact />
      </div>
    </div>
  );
}
