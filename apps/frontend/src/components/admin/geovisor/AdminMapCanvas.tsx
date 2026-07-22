"use client";

import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, useMap } from "react-leaflet";
import type { FeatureCollection, Feature } from "geojson";
import "leaflet/dist/leaflet.css";

function FitBounds({ data }: { data: FeatureCollection | null }) {
  const map = useMap();
  useEffect(() => {
    if (!data?.features?.length) {
      map.setView([8.0, -66.0], 6);
      return;
    }
    try {
      const withGeom = {
        type: "FeatureCollection" as const,
        features: data.features.filter((f) => f.geometry),
      };
      if (!withGeom.features.length) {
        map.setView([8.0, -66.0], 6);
        return;
      }
      const layer = L.geoJSON(withGeom as never);
      const bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
      else map.setView([8.0, -66.0], 6);
    } catch {
      map.setView([8.0, -66.0], 6);
    }
  }, [data, map]);
  return null;
}

const LEVEL_COLORS: Record<string, string> = {
  N1: "#0f3d31",
  N2: "#1a5f4a",
  N3: "#2a7a5f",
  N4: "#3d9a78",
  N5: "#5bb892",
};

export function AdminMapCanvas({
  data,
}: {
  data: FeatureCollection | null;
}) {
  const { polygons, points } = useMemo(() => {
    const polys: FeatureCollection = { type: "FeatureCollection", features: [] };
    const pts: Feature[] = [];
    if (!data) return { polygons: null, points: pts };
    for (const feature of data.features) {
      if (feature.geometry) polys.features.push(feature);
      else pts.push(feature);
    }
    return { polygons: polys.features.length ? polys : null, points: pts };
  }, [data]);

  return (
    <MapContainer center={[8, -66]} zoom={6} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {polygons ? (
        <GeoJSON
          key={JSON.stringify(polygons.features.map((f) => f.properties))}
          data={polygons}
          style={(feature) => {
            const level = String(feature?.properties?.level ?? "N2");
            return {
              color: LEVEL_COLORS[level] ?? "#1a5f4a",
              weight: 2,
              fillOpacity: 0.25,
            };
          }}
          onEachFeature={(feature, layer) => {
            const name = String(feature.properties?.name ?? "");
            const level = String(feature.properties?.level ?? "");
            layer.bindPopup(`<strong>${name}</strong><br/>Nivel ${level}`);
          }}
        />
      ) : null}
      {points.map((feature, index) => {
        const level = String(feature.properties?.level ?? "N1");
        const lat = 8 + (index % 5) * 0.4;
        const lng = -66 - Math.floor(index / 5) * 0.4;
        return (
          <CircleMarker
            key={`${String(feature.properties?.id ?? index)}-${level}`}
            center={[lat, lng]}
            radius={8}
            pathOptions={{
              color: LEVEL_COLORS[level] ?? "#1a5f4a",
              fillColor: LEVEL_COLORS[level] ?? "#1a5f4a",
              fillOpacity: 0.7,
            }}
          >
            <Popup>
              <strong>{String(feature.properties?.name ?? "")}</strong>
              <br />
              Nivel {level} (sin geometría)
            </Popup>
          </CircleMarker>
        );
      })}
      <FitBounds data={data} />
    </MapContainer>
  );
}
