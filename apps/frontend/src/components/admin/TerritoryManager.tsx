"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Unit = {
  id: string;
  code: string;
  name: string;
  level: string;
  parent_id?: string | null;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function TerritoryManager() {
  const [regions, setRegions] = useState<Unit[]>([]);
  const [states, setStates] = useState<Unit[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [regionForm, setRegionForm] = useState({ code: "", name: "" });
  const [stateForm, setStateForm] = useState({ code: "", name: "", parent_id: "" });

  async function load() {
    const [rRes, sRes] = await Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
    ]);
    if (rRes.ok) setRegions((await rRes.json()) as Unit[]);
    if (sRes.ok) setStates((await sRes.json()) as Unit[]);
  }

  useEffect(() => {
    void load();
  }, []);

  async function createRegion(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch(`${apiUrl()}/api/v1/admin/territory/regions`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(regionForm),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setMessage(payload.detail ?? "No se pudo crear la región.");
      return;
    }
    setRegionForm({ code: "", name: "" });
    setMessage("Región N2 creada.");
    await load();
  }

  async function createState(event: React.FormEvent) {
    event.preventDefault();
    const response = await fetch(`${apiUrl()}/api/v1/admin/territory/states`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: stateForm.code,
        name: stateForm.name,
        parent_id: stateForm.parent_id,
      }),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setMessage(payload.detail ?? "No se pudo crear el estado.");
      return;
    }
    setStateForm({ code: "", name: "", parent_id: stateForm.parent_id });
    setMessage("Estado/Seccional N3 creado.");
    await load();
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Territorio N1–N5</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            N1 es la organización. Aquí administras N2 Región y N3 Estado/Seccional (N4/N5 vía API y
            geovisor).
          </p>
        </div>
        {message ? <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm">{message}</p> : null}

        <form className="grid gap-3 md:grid-cols-3" onSubmit={(e) => void createRegion(e)}>
          <input className="input-field" placeholder="Código región" required value={regionForm.code} onChange={(e) => setRegionForm({ ...regionForm, code: e.target.value })} />
          <input className="input-field" placeholder="Nombre región" required value={regionForm.name} onChange={(e) => setRegionForm({ ...regionForm, name: e.target.value })} />
          <button className="btn btn-primary" type="submit">Crear región (N2)</button>
        </form>

        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => void createState(e)}>
          <select className="input-field" required value={stateForm.parent_id} onChange={(e) => setStateForm({ ...stateForm, parent_id: e.target.value })}>
            <option value="">Región padre</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          <input className="input-field" placeholder="Código estado" required value={stateForm.code} onChange={(e) => setStateForm({ ...stateForm, code: e.target.value })} />
          <input className="input-field" placeholder="Nombre estado" required value={stateForm.name} onChange={(e) => setStateForm({ ...stateForm, name: e.target.value })} />
          <button className="btn btn-primary" type="submit">Crear estado (N3)</button>
        </form>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="card-panel">
            <h3 className="font-semibold">Regiones (N2)</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {regions.map((r) => (
                <li key={r.id} className="flex justify-between border-b border-[var(--line)] py-2">
                  <span>{r.name}</span>
                  <span className="font-mono text-xs text-[var(--muted)]">{r.code}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card-panel">
            <h3 className="font-semibold">Estados / Seccionales (N3)</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {states.map((s) => (
                <li key={s.id} className="flex justify-between border-b border-[var(--line)] py-2">
                  <span>{s.name}</span>
                  <span className="font-mono text-xs text-[var(--muted)]">{s.code}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
