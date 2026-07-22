"use client";

import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import type { FeatureCollection } from "geojson";
import "leaflet/dist/leaflet.css";

function FitBounds({ data }: { data: FeatureCollection | null }) {
  const map = useMap();
  useEffect(() => {
    if (!data?.features?.length) {
      map.setView([8.0, -66.0], 6);
      return;
    }
    try {
      const layer = L.geoJSON(data as never);
      const bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
      else map.setView([8.0, -66.0], 6);
    } catch {
      map.setView([8.0, -66.0], 6);
    }
  }, [data, map]);
  return null;
}

export function AdminMapCanvas({
  data,
}: {
  data: FeatureCollection | null;
}) {
  const filtered = useMemo(() => {
    if (!data) return null;
    return {
      ...data,
      features: data.features.filter((f) => f.geometry),
    } as FeatureCollection;
  }, [data]);

  return (
    <MapContainer center={[8, -66]} zoom={6} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {filtered ? (
        <GeoJSON
          key={JSON.stringify(filtered.features.map((f) => f.properties))}
          data={filtered}
          style={(feature) => {
            const level = String(feature?.properties?.level ?? "N2");
            const colors: Record<string, string> = {
              N2: "#1a5f4a",
              N3: "#2a7a5f",
              N4: "#3d9a78",
              N5: "#5bb892",
            };
            return {
              color: colors[level] ?? "#1a5f4a",
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
      <FitBounds data={filtered} />
    </MapContainer>
  );
}
