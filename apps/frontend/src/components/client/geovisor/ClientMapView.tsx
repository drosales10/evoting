"use client";

import { useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/mapbox";
import type { FeatureCollection, Feature } from "geojson";
import "mapbox-gl/dist/mapbox-gl.css";

const LEVELS = ["N1", "N2", "N3", "N4", "N5"] as const;

function placeholderPosition(index: number): [number, number] {
  const lat = 8 + (index % 5) * 0.45;
  const lng = -66.1 - Math.floor(index / 5) * 0.45;
  return [lng, lat];
}

export function ClientMapView({
  data,
  mapboxToken,
}: {
  data: FeatureCollection | null;
  mapboxToken?: string;
}) {
  const token = (mapboxToken ?? process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "").trim();
  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    N1: true,
    N2: true,
    N3: true,
    N4: true,
    N5: true,
  });
  const [selected, setSelected] = useState<Feature | null>(null);

  const filteredFeatures = useMemo(() => {
    if (!data) return [];
    return data.features.filter((f) => {
      const level = String(f.properties?.level ?? "N2");
      return enabled[level] !== false;
    });
  }, [data, enabled]);

  const layers = useMemo(() => {
    const areaFeatures = filteredFeatures.filter(
      (f) => f.geometry && f.geometry.type !== "Point" && f.geometry.type !== "MultiPoint",
    );
    const pointFeatures = filteredFeatures.filter(
      (f) =>
        !f.geometry ||
        f.geometry.type === "Point" ||
        f.geometry.type === "MultiPoint",
    );
    const result = [];

    if (areaFeatures.length) {
      result.push(
        new GeoJsonLayer({
          id: "electoral-polygons",
          data: { type: "FeatureCollection", features: areaFeatures },
          filled: true,
          stroked: true,
          getFillColor: (f: Feature) => {
            const pct = Number(f.properties?.participation_pct ?? 0);
            const intensity = Math.min(255, Math.round(80 + pct * 1.5));
            return f.properties?.level === "N2"
              ? [62, 207, 154, 160]
              : [30, intensity, 140, 150];
          },
          getLineColor: [232, 242, 238, 200],
          lineWidthMinPixels: 1,
          pickable: true,
          onClick: ({ object }: { object?: Feature }) => {
            setSelected(object ?? null);
          },
        }),
      );
    }

    if (pointFeatures.length) {
      const scatterData: Array<{ feature: Feature; position: [number, number] }> = [];
      pointFeatures.forEach((feature, index) => {
        if (feature.geometry?.type === "Point") {
          const [lng, lat] = feature.geometry.coordinates;
          scatterData.push({ feature, position: [lng, lat] });
        } else if (feature.geometry?.type === "MultiPoint") {
          for (const [lng, lat] of feature.geometry.coordinates) {
            scatterData.push({ feature, position: [lng, lat] });
          }
        } else {
          scatterData.push({ feature, position: placeholderPosition(index) });
        }
      });

      result.push(
        new ScatterplotLayer({
          id: "electoral-points",
          data: scatterData,
          getPosition: (d: { position: [number, number] }) => d.position,
          getRadius: (d: { feature: Feature }) =>
            d.feature.properties?.level === "N5" ? 9000 : 12000,
          radiusUnits: "meters" as const,
          getFillColor: (d: { feature: Feature }) =>
            d.feature.properties?.level === "N5"
              ? [62, 207, 154, 220]
              : d.feature.properties?.level === "N1"
                ? [62, 207, 154, 200]
                : [90, 160, 220, 180],
          pickable: true,
          onClick: ({ object }: { object?: { feature: Feature } }) => {
            setSelected(object?.feature ?? null);
          },
        }),
      );
    }

    return result;
  }, [filteredFeatures]);

  if (!token) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-[var(--surface)] p-6 text-center text-sm text-[var(--muted)]">
        <p>
          Configura <code className="mx-1">NEXT_PUBLIC_MAPBOX_TOKEN</code> para el geovisor cliente.
        </p>
        <p>Las capas territoriales ya están disponibles vía API pública.</p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <div className="absolute left-3 top-3 z-10 space-y-2 rounded-xl border border-[var(--line)] bg-[var(--surface)]/90 p-3 backdrop-blur">
        <p className="text-xs font-extrabold uppercase tracking-wide text-[var(--muted)]">Capas</p>
        <div className="flex flex-col gap-1">
          {LEVELS.map((level) => (
            <label key={level} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enabled[level] !== false}
                onChange={() => setEnabled((prev) => ({ ...prev, [level]: !prev[level] }))}
              />
              {level}
            </label>
          ))}
        </div>
        {selected ? (
          <div className="max-w-[200px] border-t border-[var(--line)] pt-2 text-xs">
            <p className="font-semibold">{String(selected.properties?.name ?? "")}</p>
            <p className="text-[var(--muted)]">
              {String(selected.properties?.level ?? "")}
              {selected.properties?.participation_pct != null
                ? ` · ${String(selected.properties.participation_pct)}%`
                : ""}
            </p>
          </div>
        ) : null}
      </div>
      <DeckGL
        initialViewState={{ longitude: -66.1, latitude: 8.0, zoom: 5.5, pitch: 0, bearing: 0 }}
        controller
        layers={layers}
        getTooltip={({ object }: { object?: Feature | { feature: Feature } }) => {
          const feature = object && "feature" in object ? object.feature : object;
          return feature
            ? {
                html: `<strong>${String(feature.properties?.name ?? "")}</strong><br/>${String(feature.properties?.level ?? "")}${
                  feature.properties?.participation_pct != null
                    ? ` · ${String(feature.properties.participation_pct)}%`
                    : ""
                }`,
              }
            : null;
        }}
      >
        <Map mapboxAccessToken={token} mapStyle="mapbox://styles/mapbox/dark-v11" />
      </DeckGL>
    </div>
  );
}
