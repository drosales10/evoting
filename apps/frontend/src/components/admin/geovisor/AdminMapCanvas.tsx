"use client";

import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, useMap } from "react-leaflet";
import type { FeatureCollection, Feature, Geometry, Point, MultiPoint } from "geojson";
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
      if (bounds.isValid()) {
        const isSinglePoint =
          withGeom.features.length === 1 &&
          (withGeom.features[0].geometry?.type === "Point" ||
            withGeom.features[0].geometry?.type === "MultiPoint");
        if (isSinglePoint) map.setView(bounds.getCenter(), 14);
        else map.fitBounds(bounds.pad(0.15));
      } else map.setView([8.0, -66.0], 6);
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

function isPointGeometry(geometry: Geometry | null | undefined): geometry is Point | MultiPoint {
  return geometry?.type === "Point" || geometry?.type === "MultiPoint";
}

function pointCenters(geometry: Point | MultiPoint): Array<[number, number]> {
  if (geometry.type === "Point") {
    const [lng, lat] = geometry.coordinates;
    return [[lat, lng]];
  }
  return geometry.coordinates.map(([lng, lat]) => [lat, lng]);
}

function popupHtml(feature: Feature): string {
  const name = String(feature.properties?.name ?? "");
  const level = String(feature.properties?.level ?? "");
  const voted = feature.properties?.voted_count;
  const eligible = feature.properties?.eligible_count;
  const pct = feature.properties?.participation_pct;
  if (voted == null && eligible == null && pct == null) {
    return `<strong>${name}</strong><br/>Nivel ${level}`;
  }
  return (
    `<strong>${name}</strong><br/>Nivel ${level}` +
    `<br/>Votaron: ${voted ?? "—"}` +
    `<br/>Elegibles: ${eligible ?? "—"}` +
    `<br/>Participación: ${pct != null ? `${pct}%` : "—"}`
  );
}

function participationFill(feature: Feature | undefined): { color: string; fillOpacity: number } {
  const level = String(feature?.properties?.level ?? "N2");
  const base = LEVEL_COLORS[level] ?? "#1a5f4a";
  const pct = Number(feature?.properties?.participation_pct);
  if (Number.isFinite(pct) && pct > 0) {
    return { color: base, fillOpacity: Math.min(0.7, 0.15 + pct / 150) };
  }
  return { color: base, fillOpacity: 0.25 };
}

export function AdminMapCanvas({
  data,
}: {
  data: FeatureCollection | null;
}) {
  const { polygons, realPoints, placeholders } = useMemo(() => {
    const polys: FeatureCollection = { type: "FeatureCollection", features: [] };
    const real: Array<{ feature: Feature; center: [number, number] }> = [];
    const missing: Feature[] = [];
    if (!data) return { polygons: null, realPoints: real, placeholders: missing };

    for (const feature of data.features) {
      if (!feature.geometry) {
        missing.push(feature);
        continue;
      }
      if (isPointGeometry(feature.geometry)) {
        for (const center of pointCenters(feature.geometry)) {
          real.push({ feature, center });
        }
        continue;
      }
      polys.features.push(feature);
    }
    return {
      polygons: polys.features.length ? polys : null,
      realPoints: real,
      placeholders: missing,
    };
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
            const paint = participationFill(feature as Feature | undefined);
            return {
              color: paint.color,
              weight: 2,
              fillOpacity: paint.fillOpacity,
            };
          }}
          pointToLayer={(_feature, latlng) =>
            L.circleMarker(latlng, {
              radius: 8,
              color: "#5bb892",
              fillColor: "#5bb892",
              fillOpacity: 0.85,
              weight: 2,
            })
          }
          onEachFeature={(feature, layer) => {
            layer.bindPopup(popupHtml(feature));
          }}
        />
      ) : null}
      {realPoints.map(({ feature, center }, index) => {
        const level = String(feature.properties?.level ?? "N5");
        const color = LEVEL_COLORS[level] ?? "#5bb892";
        return (
          <CircleMarker
            key={`pt-${String(feature.properties?.id ?? index)}-${center[0]}-${center[1]}`}
            center={center}
            radius={level === "N5" ? 9 : 7}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Popup>
              <strong>{String(feature.properties?.name ?? "")}</strong>
              <br />
              Nivel {String(feature.properties?.level ?? "")}
              {feature.properties?.voted_count != null ||
              feature.properties?.eligible_count != null ||
              feature.properties?.participation_pct != null ? (
                <>
                  <br />
                  Votaron: {String(feature.properties?.voted_count ?? "—")}
                  <br />
                  Elegibles: {String(feature.properties?.eligible_count ?? "—")}
                  <br />
                  Participación:{" "}
                  {feature.properties?.participation_pct != null
                    ? `${String(feature.properties.participation_pct)}%`
                    : "—"}
                </>
              ) : null}
            </Popup>
          </CircleMarker>
        );
      })}
      {placeholders.map((feature, index) => {
        const level = String(feature.properties?.level ?? "N1");
        const lat = 8 + (index % 5) * 0.4;
        const lng = -66 - Math.floor(index / 5) * 0.4;
        return (
          <CircleMarker
            key={`ph-${String(feature.properties?.id ?? index)}-${level}`}
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
              {feature.properties?.participation_pct != null ? (
                <>
                  <br />
                  Participación: {String(feature.properties.participation_pct)}%
                </>
              ) : null}
            </Popup>
          </CircleMarker>
        );
      })}
      <FitBounds data={data} />
    </MapContainer>
  );
}
