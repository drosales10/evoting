"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import type { FeatureCollection } from "geojson";

import { DashboardShell } from "@/components/admin/DashboardShell";

const AdminMapCanvas = dynamic(
  () => import("@/components/admin/geovisor/AdminMapCanvas").then((m) => m.AdminMapCanvas),
  { ssr: false, loading: () => <p className="text-sm text-[var(--muted)]">Cargando mapa…</p> },
);

type TerritoryUnit = { id: string; code: string; name: string; level: string };
type Election = { id: string; title: string; status: string };

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

function AdminGeovisorInner() {
  const searchParams = useSearchParams();
  const requestedElection = searchParams.get("election") ?? "";
  const [data, setData] = useState<FeatureCollection | null>(null);
  const [levels, setLevels] = useState("N1,N2,N3,N4,N5");
  const [message, setMessage] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [organization, setOrganization] = useState<TerritoryUnit | null>(null);
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [municipalities, setMunicipalities] = useState<TerritoryUnit[]>([]);
  const [pollingPlaces, setPollingPlaces] = useState<TerritoryUnit[]>([]);
  const [elections, setElections] = useState<Election[]>([]);
  const [electionId, setElectionId] = useState(requestedElection);
  const [importTarget, setImportTarget] = useState({ level: "N1", id: "" });

  const load = useCallback(async () => {
    const territoryRes = await fetch(
      `${apiUrl()}/api/v1/admin/geo/features?levels=${encodeURIComponent(levels)}`,
      { credentials: "include", cache: "no-store" },
    );
    if (!territoryRes.ok) {
      setMessage("No se pudieron cargar las capas territoriales.");
      return;
    }
    const territory = (await territoryRes.json()) as FeatureCollection;

    let results: FeatureCollection | null = null;
    if (electionId) {
      const resultsRes = await fetch(`${apiUrl()}/api/v1/admin/geo/results/${electionId}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (resultsRes.ok) {
        results = (await resultsRes.json()) as FeatureCollection;
      }
    }

    setData(mergeCollections(territory, results));
    setMessage(null);
    setInfo(
      results
        ? "Overlay de participación (votaron / elegibles / %) activo."
        : electionId
          ? "Elección sin tally TALLIED: solo territorio."
          : "Modo territorio. Selecciona una elección TALLIED para ver participación.",
    );
  }, [electionId, levels]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/organization`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/municipalities`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/polling-places`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/elections`, { credentials: "include" }),
    ])
      .then(async ([oRes, rRes, sRes, mRes, pRes, eRes]) => {
        if (oRes.ok) {
          const org = (await oRes.json()) as TerritoryUnit;
          setOrganization(org);
          setImportTarget((current) =>
            current.level === "N1" && !current.id ? { level: "N1", id: org.id } : current,
          );
        }
        if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
        if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
        if (mRes.ok) setMunicipalities((await mRes.json()) as TerritoryUnit[]);
        if (pRes.ok) setPollingPlaces((await pRes.json()) as TerritoryUnit[]);
        if (eRes.ok) {
          const list = (await eRes.json()) as Election[];
          setElections(list);
          if (!requestedElection) {
            const preferred =
              list.find((e) => e.status === "TALLIED") ??
              list.find((e) => e.status === "CLOSED") ??
              list[0];
            if (preferred) setElectionId(preferred.id);
          }
        }
      })
      .catch(() => undefined);
  }, [requestedElection]);

  const unitsForLevel =
    importTarget.level === "N1"
      ? organization
        ? [organization]
        : []
      : importTarget.level === "N2"
        ? regions
        : importTarget.level === "N3"
          ? states
          : importTarget.level === "N4"
            ? municipalities
            : pollingPlaces;

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
    setMessage(`GeoJSON importado en ${importTarget.level}.`);
    await load();
  }

  return (
    <DashboardShell>
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Geovisor administrativo</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Leaflet + OSM · territorio N1–N5 e overlay de participación electoral.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[240px] flex-1 text-sm font-bold">
            Elección (participación)
            <select
              className="input-field mt-1"
              value={electionId}
              onChange={(e) => setElectionId(e.target.value)}
            >
              <option value="">Solo territorio</option>
              {elections.map((election) => (
                <option key={election.id} value={election.id}>
                  {election.title} ({election.status})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          {["N1,N2,N3", "N2,N3", "N2,N3,N4", "N2,N3,N4,N5", "N1,N2,N3,N4,N5"].map((preset) => (
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
              onChange={(e) => {
                const level = e.target.value;
                const nextId = level === "N1" && organization ? organization.id : "";
                setImportTarget({ level, id: nextId });
              }}
            >
              <option value="N1">N1 Organización</option>
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
              {unitsForLevel.map((unit) => (
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
        {info ? <p className="text-sm text-[var(--muted)]">{info}</p> : null}
        <div className="h-[520px] overflow-hidden rounded-xl border border-[var(--line)]">
          <AdminMapCanvas data={data} />
        </div>
        <p className="text-xs text-[var(--muted)]">
          Features: {data?.features.length ?? 0}. Popups muestran votaron / elegibles / % cuando hay
          tally.
        </p>
      </div>
    </DashboardShell>
  );
}

export function AdminGeovisorPage() {
  return (
    <Suspense fallback={<DashboardShell><p className="text-sm text-[var(--muted)]">Cargando geovisor…</p></DashboardShell>}>
      <AdminGeovisorInner />
    </Suspense>
  );
}
