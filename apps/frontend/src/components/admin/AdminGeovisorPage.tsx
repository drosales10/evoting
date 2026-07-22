"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import type { FeatureCollection } from "geojson";

import { DashboardShell } from "@/components/admin/DashboardShell";

const AdminMapCanvas = dynamic(
  () => import("@/components/admin/geovisor/AdminMapCanvas").then((m) => m.AdminMapCanvas),
  { ssr: false, loading: () => <p className="text-sm text-[var(--muted)]">Cargando mapa…</p> },
);

type TerritoryUnit = { id: string; code: string; name: string; level: string };

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AdminGeovisorPage() {
  const [data, setData] = useState<FeatureCollection | null>(null);
  const [levels, setLevels] = useState("N2,N3,N4,N5");
  const [message, setMessage] = useState<string | null>(null);
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [municipalities, setMunicipalities] = useState<TerritoryUnit[]>([]);
  const [pollingPlaces, setPollingPlaces] = useState<TerritoryUnit[]>([]);
  const [importTarget, setImportTarget] = useState({ level: "N2", id: "" });

  const load = useCallback(async () => {
    const response = await fetch(
      `${apiUrl()}/api/v1/admin/geo/features?levels=${encodeURIComponent(levels)}`,
      { credentials: "include", cache: "no-store" },
    );
    if (!response.ok) {
      setMessage("No se pudieron cargar las capas territoriales.");
      return;
    }
    setData((await response.json()) as FeatureCollection);
    setMessage(null);
  }, [levels]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/municipalities`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/polling-places`, { credentials: "include" }),
    ])
      .then(async ([rRes, sRes, mRes, pRes]) => {
        if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
        if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
        if (mRes.ok) setMunicipalities((await mRes.json()) as TerritoryUnit[]);
        if (pRes.ok) setPollingPlaces((await pRes.json()) as TerritoryUnit[]);
      })
      .catch(() => undefined);
  }, []);

  async function importGeojson(file: File) {
    if (!importTarget.id) {
      setMessage("Selecciona una unidad territorial destino.");
      return;
    }
    const text = await file.text();
    let payload: unknown;
    try {
      payload = JSON.parse(text);
    } catch {
      setMessage("El archivo no es JSON válido.");
      return;
    }
    const response = await fetch(
      `${apiUrl()}/api/v1/admin/territory/${importTarget.level}/${importTarget.id}/geojson`,
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    if (!response.ok) {
      const err = (await response.json()) as { detail?: string };
      setMessage(err.detail ?? "No se pudo importar el GeoJSON.");
      return;
    }
    setMessage("GeoJSON importado.");
    await load();
  }

  return (
    <DashboardShell>
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Geovisor administrativo</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Leaflet + OSM · capas N1–N5 del territorio electoral.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {["N2,N3", "N2,N3,N4", "N2,N3,N4,N5", "N1,N2,N3,N4,N5"].map((preset) => (
            <button
              key={preset}
              type="button"
              className="btn btn-secondary"
              onClick={() => setLevels(preset)}
            >
              {preset}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-dashed border-[var(--line)] p-3">
          <label className="text-sm font-bold">
            Nivel
            <select
              className="input-field mt-1"
              value={importTarget.level}
              onChange={(e) => setImportTarget({ level: e.target.value, id: "" })}
            >
              <option value="N2">N2 Región</option>
              <option value="N3">N3 Estado</option>
              <option value="N4">N4 Municipio</option>
              <option value="N5">N5 Mesa</option>
            </select>
          </label>
          <label className="min-w-[200px] flex-1 text-sm font-bold">
            Unidad
            <select
              className="input-field mt-1"
              value={importTarget.id}
              onChange={(e) => setImportTarget({ ...importTarget, id: e.target.value })}
            >
              <option value="">Seleccionar…</option>
              {(
                importTarget.level === "N2"
                  ? regions
                  : importTarget.level === "N3"
                    ? states
                    : importTarget.level === "N4"
                      ? municipalities
                      : pollingPlaces
              ).map((unit) => (
                <option key={unit.id} value={unit.id}>
                  {unit.name} ({unit.code})
                </option>
              ))}
            </select>
          </label>
          <label className="btn btn-secondary cursor-pointer">
            Importar GeoJSON
            <input
              type="file"
              accept=".json,.geojson,application/geo+json,application/json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importGeojson(file);
              }}
            />
          </label>
        </div>
        {message ? <p className="text-sm text-red-600 dark:text-amber-300">{message}</p> : null}
        <div className="h-[520px] overflow-hidden rounded-xl border border-[var(--line)]">
          <AdminMapCanvas data={data} />
        </div>
        <p className="text-xs text-[var(--muted)]">
          Features: {data?.features.length ?? 0}. También puedes usar PUT
          /api/v1/admin/territory/{"{level}"}/{"{id}"}/geojson
        </p>
      </div>
    </DashboardShell>
  );
}
