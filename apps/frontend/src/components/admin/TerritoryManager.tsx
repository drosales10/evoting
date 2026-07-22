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
  const [municipalities, setMunicipalities] = useState<Unit[]>([]);
  const [pollingPlaces, setPollingPlaces] = useState<Unit[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [regionForm, setRegionForm] = useState({ code: "", name: "" });
  const [stateForm, setStateForm] = useState({ code: "", name: "", parent_id: "" });
  const [muniForm, setMuniForm] = useState({ code: "", name: "", parent_id: "" });
  const [placeForm, setPlaceForm] = useState({ code: "", name: "", parent_id: "" });

  async function load() {
    const [rRes, sRes, mRes, pRes] = await Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/municipalities`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/polling-places`, { credentials: "include" }),
    ]);
    if (rRes.ok) setRegions((await rRes.json()) as Unit[]);
    if (sRes.ok) setStates((await sRes.json()) as Unit[]);
    if (mRes.ok) setMunicipalities((await mRes.json()) as Unit[]);
    if (pRes.ok) setPollingPlaces((await pRes.json()) as Unit[]);
  }

  useEffect(() => {
    void load();
  }, []);

  async function createUnit(
    path: string,
    body: Record<string, string>,
    okMessage: string,
    reset: () => void,
  ) {
    const response = await fetch(`${apiUrl()}/api/v1/admin/territory/${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      setMessage(payload.detail ?? `No se pudo crear (${path}).`);
      return;
    }
    reset();
    setMessage(okMessage);
    await load();
  }

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Territorio N1–N5</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            N1 es la organización. Administra N2 Región → N3 Estado → N4 Municipio → N5 Mesa.
          </p>
        </div>
        {message ? <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm">{message}</p> : null}

        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            void createUnit("regions", regionForm, "Región N2 creada.", () =>
              setRegionForm({ code: "", name: "" }),
            );
          }}
        >
          <input className="input-field" placeholder="Código región" required value={regionForm.code} onChange={(e) => setRegionForm({ ...regionForm, code: e.target.value })} />
          <input className="input-field" placeholder="Nombre región" required value={regionForm.name} onChange={(e) => setRegionForm({ ...regionForm, name: e.target.value })} />
          <button className="btn btn-primary" type="submit">Crear región (N2)</button>
        </form>

        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            void createUnit(
              "states",
              { code: stateForm.code, name: stateForm.name, parent_id: stateForm.parent_id },
              "Estado/Seccional N3 creado.",
              () => setStateForm({ code: "", name: "", parent_id: stateForm.parent_id }),
            );
          }}
        >
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

        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            void createUnit(
              "municipalities",
              { code: muniForm.code, name: muniForm.name, parent_id: muniForm.parent_id },
              "Municipio N4 creado.",
              () => setMuniForm({ code: "", name: "", parent_id: muniForm.parent_id }),
            );
          }}
        >
          <select className="input-field" required value={muniForm.parent_id} onChange={(e) => setMuniForm({ ...muniForm, parent_id: e.target.value })}>
            <option value="">Estado padre</option>
            {states.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <input className="input-field" placeholder="Código municipio" required value={muniForm.code} onChange={(e) => setMuniForm({ ...muniForm, code: e.target.value })} />
          <input className="input-field" placeholder="Nombre municipio" required value={muniForm.name} onChange={(e) => setMuniForm({ ...muniForm, name: e.target.value })} />
          <button className="btn btn-primary" type="submit">Crear municipio (N4)</button>
        </form>

        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault();
            void createUnit(
              "polling-places",
              { code: placeForm.code, name: placeForm.name, parent_id: placeForm.parent_id },
              "Mesa/centro N5 creado.",
              () => setPlaceForm({ code: "", name: "", parent_id: placeForm.parent_id }),
            );
          }}
        >
          <select className="input-field" required value={placeForm.parent_id} onChange={(e) => setPlaceForm({ ...placeForm, parent_id: e.target.value })}>
            <option value="">Municipio padre</option>
            {municipalities.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
          <input className="input-field" placeholder="Código mesa" required value={placeForm.code} onChange={(e) => setPlaceForm({ ...placeForm, code: e.target.value })} />
          <input className="input-field" placeholder="Nombre mesa" required value={placeForm.name} onChange={(e) => setPlaceForm({ ...placeForm, name: e.target.value })} />
          <button className="btn btn-primary" type="submit">Crear mesa (N5)</button>
        </form>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            { title: "Regiones (N2)", items: regions },
            { title: "Estados (N3)", items: states },
            { title: "Municipios (N4)", items: municipalities },
            { title: "Mesas (N5)", items: pollingPlaces },
          ].map((block) => (
            <div key={block.title} className="card-panel">
              <h3 className="font-semibold">{block.title}</h3>
              <ul className="mt-3 max-h-56 space-y-2 overflow-y-auto text-sm">
                {block.items.length === 0 ? (
                  <li className="text-[var(--muted)]">Vacío</li>
                ) : (
                  block.items.map((unit) => (
                    <li key={unit.id} className="flex justify-between border-b border-[var(--line)] py-2">
                      <span>{unit.name}</span>
                      <span className="font-mono text-xs text-[var(--muted)]">{unit.code}</span>
                    </li>
                  ))
                )}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
