"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";
import { AdminOverview } from "@/components/admin/admin-overview";

type TerritoryUnit = { id: string; code: string; name: string; parent_id?: string | null };
type Election = {
  id: string;
  title: string;
  status: string;
  scope_level?: string;
  region_id?: string | null;
  state_id?: string | null;
  start_time: string;
  quorum_threshold_pct: string;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ElectionsManager() {
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [elections, setElections] = useState<Election[]>([]);
  const [scope, setScope] = useState<"NATIONAL" | "REGIONAL" | "STATE">("NATIONAL");
  const [regionId, setRegionId] = useState("");
  const [stateId, setStateId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const statesForRegion = useMemo(
    () => states.filter((s) => !regionId || s.parent_id === regionId),
    [states, regionId],
  );

  async function load() {
    const [rRes, sRes, eRes] = await Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/elections`, { credentials: "include" }),
    ]);
    if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
    if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
    if (eRes.ok) setElections((await eRes.json()) as Election[]);
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/elections`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: String(form.get("title") ?? "").trim(),
          voting_type: "SLATE_PLURALITY",
          start_time: new Date(String(form.get("start_time") ?? "")).toISOString(),
          end_time: new Date(String(form.get("end_time") ?? "")).toISOString(),
          quorum_threshold_pct: Number(form.get("quorum_threshold_pct") ?? 30),
          scope_level: scope,
          region_id: scope === "REGIONAL" || scope === "STATE" ? regionId || null : null,
          state_id: scope === "STATE" ? stateId || null : null,
        }),
      });
      const payload = (await response.json()) as Election & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo crear la elección.");
        return;
      }
      setMessage(`Elección creada con alcance ${payload.scope_level ?? scope}.`);
      event.currentTarget.reset();
      setScope("NATIONAL");
      setRegionId("");
      setStateId("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  const grouped = useMemo(() => {
    const buckets: Record<string, Election[]> = {
      NATIONAL: [],
      REGIONAL: [],
      STATE: [],
    };
    for (const election of elections) {
      const key = election.scope_level ?? "NATIONAL";
      if (!buckets[key]) buckets[key] = [];
      buckets[key].push(election);
    }
    return buckets;
  }, [elections]);

  return (
    <DashboardShell>
      <div className="space-y-8">
        <div>
          <h2 className="text-xl font-semibold">Elecciones por alcance territorial</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            NATIONAL (toda la org), REGIONAL (N2) o STATE (N3). Al abrir registro, el snapshot se
            filtra por el territorio de la elección.
          </p>
        </div>

        <form className="grid gap-3 rounded-xl border border-[var(--line)] p-4 md:grid-cols-2" onSubmit={(e) => void handleCreate(e)}>
          <label className="text-sm font-bold md:col-span-2">
            Título
            <input className="input-field mt-1" name="title" minLength={3} required />
          </label>
          <label className="text-sm font-bold">
            Inicio
            <input className="input-field mt-1" name="start_time" type="datetime-local" required />
          </label>
          <label className="text-sm font-bold">
            Fin
            <input className="input-field mt-1" name="end_time" type="datetime-local" required />
          </label>
          <label className="text-sm font-bold">
            Quórum (%)
            <input
              className="input-field mt-1"
              name="quorum_threshold_pct"
              type="number"
              min={0}
              max={100}
              step="0.01"
              defaultValue={30}
              required
            />
          </label>
          <label className="text-sm font-bold">
            Alcance
            <select
              className="input-field mt-1"
              value={scope}
              onChange={(e) => setScope(e.target.value as typeof scope)}
            >
              <option value="NATIONAL">Nacional (N1)</option>
              <option value="REGIONAL">Regional (N2)</option>
              <option value="STATE">Estatal / Seccional (N3)</option>
            </select>
          </label>
          {scope !== "NATIONAL" ? (
            <label className="text-sm font-bold">
              Región
              <select
                className="input-field mt-1"
                required
                value={regionId}
                onChange={(e) => {
                  setRegionId(e.target.value);
                  setStateId("");
                }}
              >
                <option value="">Seleccionar región</option>
                {regions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {scope === "STATE" ? (
            <label className="text-sm font-bold">
              Estado / Seccional
              <select
                className="input-field mt-1"
                required
                value={stateId}
                onChange={(e) => setStateId(e.target.value)}
              >
                <option value="">Seleccionar estado</option>
                {statesForRegion.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="md:col-span-2">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Creando…" : "Crear elección DRAFT"}
            </button>
          </div>
        </form>

        {message ? <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm">{message}</p> : null}

        <div className="grid gap-4 lg:grid-cols-3">
          {(["NATIONAL", "REGIONAL", "STATE"] as const).map((key) => (
            <section key={key} className="card-panel">
              <h3 className="font-semibold">{key}</h3>
              <ul className="mt-3 space-y-2 text-sm">
                {(grouped[key] ?? []).length === 0 ? (
                  <li className="text-[var(--muted)]">Sin elecciones</li>
                ) : (
                  (grouped[key] ?? []).map((election) => (
                    <li key={election.id} className="border-b border-[var(--line)] py-2">
                      <p className="font-semibold">{election.title}</p>
                      <p className="text-xs text-[var(--muted)]">{election.status}</p>
                    </li>
                  ))
                )}
              </ul>
            </section>
          ))}
        </div>

        <div className="border-t border-[var(--line)] pt-6">
          <h3 className="text-lg font-semibold">Ciclo electoral (registro → escrutinio)</h3>
          <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
            Usa las acciones por elección para abrir registro, congelar, activar y cerrar.
          </p>
          <AdminOverview focus="elections" />
        </div>
      </div>
    </DashboardShell>
  );
}
