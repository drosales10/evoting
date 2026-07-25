"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { CeremonyAdminPanel } from "@/components/admin/CeremonyAdminPanel";
import { DashboardShell } from "@/components/admin/DashboardShell";
import {
  AdminOverview,
  type ElectionsTab,
} from "@/components/admin/admin-overview";

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

const TABS: Array<{ id: ElectionsTab; label: string; hint: string }> = [
  {
    id: "ciclo",
    label: "Ciclo electoral",
    hint: "Registro → congelar → activar → cerrar → escrutinio",
  },
  {
    id: "procesos",
    label: "Procesos registrados",
    hint: "Listado por alcance territorial",
  },
  {
    id: "crear",
    label: "Crear elección",
    hint: "Nueva elección en estado DRAFT",
  },
  {
    id: "planchas",
    label: "Gestionar planchas",
    hint: "Planchas y lemas en registro",
  },
  {
    id: "estructura",
    label: "Estructura de elección",
    hint: "Cargos / posiciones (DRAFT o REGISTRATION)",
  },
  {
    id: "elegibles",
    label: "Asignar elegibles",
    hint: "Candidatos a cargos y snapshot de elegibilidad",
  },
];

const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Borrador",
  REGISTRATION: "Registro",
  FREEZE: "Congelada",
  ACTIVE: "Activa",
  CLOSED: "Cerrada",
  TALLIED: "Escrutada",
};

function statusClass(status: string): string {
  switch (status) {
    case "DRAFT":
      return "elections-status elections-status--draft";
    case "REGISTRATION":
      return "elections-status elections-status--registration";
    case "FREEZE":
      return "elections-status elections-status--freeze";
    case "ACTIVE":
      return "elections-status elections-status--active";
    case "CLOSED":
      return "elections-status elections-status--closed";
    case "TALLIED":
      return "elections-status elections-status--tallied";
    default:
      return "elections-status";
  }
}

export function ElectionsManager() {
  const [tab, setTab] = useState<ElectionsTab>("ciclo");
  const [focusElectionId, setFocusElectionId] = useState<string | null>(null);
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [elections, setElections] = useState<Election[]>([]);
  const [scope, setScope] = useState<"NATIONAL" | "REGIONAL" | "STATE">("NATIONAL");
  const [regionId, setRegionId] = useState("");
  const [stateId, setStateId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ceremonyElectionId, setCeremonyElectionId] = useState("");
  const [overviewKey, setOverviewKey] = useState(0);

  const statesForRegion = useMemo(
    () => states.filter((s) => !regionId || s.parent_id === regionId),
    [states, regionId],
  );

  const ceremonyElection = useMemo(
    () => elections.find((e) => e.id === ceremonyElectionId) ?? null,
    [elections, ceremonyElectionId],
  );

  const ceremonyCandidates = useMemo(
    () =>
      elections.filter((e) =>
        ["REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED"].includes(e.status),
      ),
    [elections],
  );

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

  const activeTab = TABS.find((item) => item.id === tab) ?? TABS[0];

  async function load() {
    const [rRes, sRes, eRes] = await Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/elections`, { credentials: "include" }),
    ]);
    if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
    if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
    if (eRes.ok) {
      const list = (await eRes.json()) as Election[];
      setElections(list);
      setCeremonyElectionId((current) => {
        if (current && list.some((e) => e.id === current)) return current;
        const preferred =
          list.find((e) => e.status === "CLOSED") ??
          list.find((e) => e.status === "ACTIVE") ??
          list.find((e) => e.status === "TALLIED") ??
          list.find((e) =>
            ["REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED"].includes(e.status),
          );
        return preferred?.id ?? "";
      });
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const navigateTab = useCallback((next: ElectionsTab, electionId?: string) => {
    setTab(next);
    if (electionId) setFocusElectionId(electionId);
    if (electionId && ["REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED"].includes(
      elections.find((e) => e.id === electionId)?.status ?? "",
    )) {
      setCeremonyElectionId(electionId);
    }
  }, [elections]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setBusy(true);
    setMessage(null);
    const form = new FormData(formElement);
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
      formElement.reset();
      setScope("NATIONAL");
      setRegionId("");
      setStateId("");
      await load();
      setOverviewKey((k) => k + 1);
      setFocusElectionId(payload.id);
      setTab("estructura");
    } finally {
      setBusy(false);
    }
  }

  return (
    <DashboardShell>
      <div className="elections-module">
        <header className="elections-module__header">
          <div>
            <p className="eyebrow">Comisión electoral</p>
            <h2 className="elections-module__title">Elecciones</h2>
            <p className="elections-module__lead">
              Organiza el ciclo completo: crear, estructurar cargos, registrar planchas, asignar
              elegibles y llevar el proceso hasta el escrutinio.
            </p>
          </div>
          <div className="elections-module__meta" aria-label="Resumen rápido">
            <div>
              <span className="elections-module__meta-label">Procesos</span>
              <strong>{elections.length}</strong>
            </div>
            <div>
              <span className="elections-module__meta-label">Activas</span>
              <strong>{elections.filter((e) => e.status === "ACTIVE").length}</strong>
            </div>
          </div>
        </header>

        <nav className="elections-tabs" aria-label="Secciones del módulo de elecciones">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={`elections-tabs__btn${tab === item.id ? " is-active" : ""}`}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <p className="elections-tabs__hint">{activeTab.hint}</p>

        <div className="elections-panel" role="tabpanel">
          {tab === "ciclo" ? (
            <div className="space-y-6">
              <section
                id="ceremonia-escrutinio"
                className="scroll-mt-6 space-y-4 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5 dark:bg-[var(--surface)]"
              >
                <div>
                  <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
                    Portal público
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">Ceremonia de escrutinio (YouTube)</h3>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Configura el live que verán miembros y público en el geovisor cliente y en
                    resultados.
                  </p>
                </div>
                {ceremonyCandidates.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-[var(--line)] px-4 py-6 text-sm text-[var(--muted)]">
                    No hay elecciones listas para ceremonia. Crea una y ábrela al menos en registro.
                  </p>
                ) : (
                  <>
                    <label className="block max-w-xl text-sm font-bold">
                      Elección
                      <select
                        className="input-field mt-1"
                        value={ceremonyElectionId}
                        onChange={(e) => setCeremonyElectionId(e.target.value)}
                      >
                        <option value="">Selecciona una elección</option>
                        {ceremonyCandidates.map((election) => (
                          <option key={election.id} value={election.id}>
                            {election.title} · {STATUS_LABEL[election.status] ?? election.status}
                          </option>
                        ))}
                      </select>
                    </label>
                    {ceremonyElection ? (
                      <CeremonyAdminPanel
                        electionId={ceremonyElection.id}
                        electionTitle={ceremonyElection.title}
                      />
                    ) : null}
                  </>
                )}
              </section>

              <AdminOverview
                key={`ciclo-${overviewKey}`}
                focus="elections"
                electionsTab="ciclo"
                focusElectionId={focusElectionId}
                onNavigateTab={navigateTab}
              />
            </div>
          ) : null}

          {tab === "procesos" ? (
            <div className="space-y-6">
              <div className="grid gap-4 lg:grid-cols-3">
                {(["NATIONAL", "REGIONAL", "STATE"] as const).map((key) => (
                  <section key={key} className="card-panel">
                    <h3 className="font-semibold">
                      {key === "NATIONAL" ? "Nacional" : key === "REGIONAL" ? "Regional" : "Estatal"}
                    </h3>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {(grouped[key] ?? []).length} proceso
                      {(grouped[key] ?? []).length === 1 ? "" : "s"}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm">
                      {(grouped[key] ?? []).length === 0 ? (
                        <li className="text-[var(--muted)]">Sin elecciones</li>
                      ) : (
                        (grouped[key] ?? []).map((election) => (
                          <li key={election.id} className="border-b border-[var(--line)] py-2 last:border-0">
                            <p className="font-semibold">{election.title}</p>
                            <span className={statusClass(election.status)}>
                              {STATUS_LABEL[election.status] ?? election.status}
                            </span>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                type="button"
                                className="text-xs font-bold text-[var(--primary)] underline"
                                onClick={() => navigateTab("ciclo", election.id)}
                              >
                                Ver ciclo
                              </button>
                              {election.status === "DRAFT" || election.status === "REGISTRATION" ? (
                                <button
                                  type="button"
                                  className="text-xs font-bold text-[var(--primary)] underline"
                                  onClick={() => navigateTab("estructura", election.id)}
                                >
                                  Estructura
                                </button>
                              ) : null}
                              {election.status === "REGISTRATION" || election.status === "FREEZE" ? (
                                <>
                                  <button
                                    type="button"
                                    className="text-xs font-bold text-[var(--primary)] underline"
                                    onClick={() => navigateTab("planchas", election.id)}
                                  >
                                    Planchas
                                  </button>
                                  <button
                                    type="button"
                                    className="text-xs font-bold text-[var(--primary)] underline"
                                    onClick={() => navigateTab("elegibles", election.id)}
                                  >
                                    Elegibles
                                  </button>
                                </>
                              ) : null}
                            </div>
                          </li>
                        ))
                      )}
                    </ul>
                  </section>
                ))}
              </div>
              {elections.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[var(--line)] px-4 py-8 text-center text-sm text-[var(--muted)]">
                  Aún no hay procesos. Usa la pestaña <strong>Crear elección</strong> para iniciar uno.
                </p>
              ) : null}
            </div>
          ) : null}

          {tab === "crear" ? (
            <section className="elections-create card-panel max-w-3xl">
              <h3 className="text-lg font-semibold">Crear elección DRAFT</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">
                La elección nace en borrador. Luego define la estructura de cargos y abre el
                registro.
              </p>
              <form
                className="mt-4 grid gap-3 md:grid-cols-2"
                onSubmit={(e) => void handleCreate(e)}
              >
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
              {message ? (
                <p className="mt-4 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm dark:bg-[var(--accent)]">
                  {message}
                </p>
              ) : null}
            </section>
          ) : null}

          {tab === "planchas" || tab === "estructura" || tab === "elegibles" ? (
            <AdminOverview
              key={`${tab}-${overviewKey}-${focusElectionId ?? "none"}`}
              focus="elections"
              electionsTab={tab}
              focusElectionId={focusElectionId}
              onNavigateTab={navigateTab}
            />
          ) : null}
        </div>
      </div>
    </DashboardShell>
  );
}
