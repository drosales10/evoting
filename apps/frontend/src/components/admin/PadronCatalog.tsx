"use client";

import { useCallback, useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Member = {
  id: string;
  registry_code: string | null;
  full_name: string;
  dni: string;
  email: string;
  status: string;
  region: string | null;
  section: string | null;
  location: string | null;
  alive: boolean | null;
  region_id?: string | null;
  state_id?: string | null;
};

type MemberList = {
  items: Member[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
};

type TerritoryUnit = { id: string; code: string; name: string; parent_id?: string | null };

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function PadronCatalog() {
  const [query, setQuery] = useState("");
  const [regionId, setRegionId] = useState("");
  const [stateId, setStateId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<MemberList | null>(null);
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    dni: "",
    membership_months: "0",
    region: "",
    section: "",
    region_id: "",
    state_id: "",
  });

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        limit: "25",
        sort: "full_name",
      });
      if (query.trim()) params.set("q", query.trim());
      if (regionId) params.set("region_id", regionId);
      if (stateId) params.set("state_id", stateId);
      const response = await fetch(`${apiUrl()}/api/v1/admin/members?${params}`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json()) as MemberList & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cargar el padrón.");
        return;
      }
      setData(payload);
      setMessage(null);
    } catch {
      setMessage("Error de red al cargar el padrón.");
    } finally {
      setBusy(false);
    }
  }, [page, query, regionId, stateId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void load();
    }, 300);
    return () => window.clearTimeout(handle);
  }, [load]);

  useEffect(() => {
    void Promise.all([
      fetch(`${apiUrl()}/api/v1/admin/territory/regions`, { credentials: "include" }),
      fetch(`${apiUrl()}/api/v1/admin/territory/states`, { credentials: "include" }),
    ]).then(async ([rRes, sRes]) => {
      if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
      if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
    });
  }, []);

  async function createMember(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const selectedRegion = regions.find((r) => r.id === form.region_id);
      const selectedState = states.find((s) => s.id === form.state_id);
      const response = await fetch(`${apiUrl()}/api/v1/admin/members`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          full_name: form.full_name,
          dni: form.dni,
          membership_months: Number(form.membership_months) || 0,
          region: form.region.trim() || selectedRegion?.name || null,
          section: form.section.trim() || selectedState?.name || null,
          region_id: form.region_id || null,
          state_id: form.state_id || null,
        }),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo crear el miembro.");
        return;
      }
      setForm({
        email: "",
        full_name: "",
        dni: "",
        membership_months: "0",
        region: "",
        section: "",
        region_id: "",
        state_id: "",
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function importFile(file: File, dryRun: boolean) {
    setBusy(true);
    const body = new FormData();
    body.append("file", file);
    body.append("dry_run", String(dryRun));
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members/import`, {
        method: "POST",
        credentials: "include",
        body,
      });
      const payload = (await response.json()) as {
        created?: number;
        updated?: number;
        failed?: number;
        detail?: string;
      };
      if (!response.ok) {
        setMessage(payload.detail ?? "Importación fallida.");
        return;
      }
      setMessage(
        `${dryRun ? "Validación" : "Importación"}: +${payload.created ?? 0} / ~${payload.updated ?? 0} / fallos ${payload.failed ?? 0}`,
      );
      if (!dryRun) await load();
    } finally {
      setBusy(false);
    }
  }

  const filteredStates = states.filter((s) => !regionId || s.parent_id === regionId);
  const formStates = states.filter((s) => !form.region_id || s.parent_id === form.region_id);

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Padrón administrativo</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Catálogo paginado con búsqueda, filtros territoriales e importación XLSX (Región /
            Seccional → FKs).
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[200px] flex-1 text-sm font-bold">
            Buscar
            <input
              className="input-field mt-1"
              value={query}
              onChange={(e) => {
                setPage(1);
                setQuery(e.target.value);
              }}
              placeholder="Código, DNI, nombre, región…"
            />
          </label>
          <label className="min-w-[160px] text-sm font-bold">
            Región
            <select
              className="input-field mt-1"
              value={regionId}
              onChange={(e) => {
                setPage(1);
                setRegionId(e.target.value);
                setStateId("");
              }}
            >
              <option value="">Todas</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[160px] text-sm font-bold">
            Estado
            <select
              className="input-field mt-1"
              value={stateId}
              onChange={(e) => {
                setPage(1);
                setStateId(e.target.value);
              }}
            >
              <option value="">Todos</option>
              {filteredStates.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <a className="btn btn-secondary" href={`${apiUrl()}/api/v1/admin/members/export`}>
            Exportar XLSX
          </a>
          <label className="btn btn-secondary cursor-pointer">
            Importar
            <input
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importFile(file, false);
              }}
            />
          </label>
          <label className="btn btn-secondary cursor-pointer">
            Solo validar
            <input
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importFile(file, true);
              }}
            />
          </label>
        </div>

        <form
          className="grid gap-3 rounded-xl border border-dashed border-[var(--line)] p-4 md:grid-cols-3 lg:grid-cols-6"
          onSubmit={(e) => void createMember(e)}
        >
          <input className="input-field" placeholder="Nombre completo" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <input className="input-field" placeholder="Documento" required value={form.dni} onChange={(e) => setForm({ ...form, dni: e.target.value })} />
          <input className="input-field" placeholder="Correo" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <select
            className="input-field"
            value={form.region_id}
            onChange={(e) => setForm({ ...form, region_id: e.target.value, state_id: "" })}
          >
            <option value="">Región (opcional)</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <select
            className="input-field"
            value={form.state_id}
            onChange={(e) => setForm({ ...form, state_id: e.target.value })}
          >
            <option value="">Estado (opcional)</option>
            {formStates.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Alta rápida
          </button>
        </form>

        {message ? <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm text-[var(--primary-dark)]">{message}</p> : null}

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[var(--muted)]">
              <tr>
                <th className="px-2 py-2">Código</th>
                <th className="px-2 py-2">Nombre</th>
                <th className="px-2 py-2">Documento</th>
                <th className="px-2 py-2">Región</th>
                <th className="px-2 py-2">Seccional</th>
                <th className="px-2 py-2">Estado</th>
                <th className="px-2 py-2">Vivo</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((member) => (
                <tr key={member.id} className="border-b border-[var(--line)]/70">
                  <td className="px-2 py-2 font-mono text-xs">{member.registry_code ?? "—"}</td>
                  <td className="px-2 py-2 font-semibold">{member.full_name}</td>
                  <td className="px-2 py-2">{member.dni}</td>
                  <td className="px-2 py-2">{member.region ?? "—"}</td>
                  <td className="px-2 py-2">{member.section ?? "—"}</td>
                  <td className="px-2 py-2">{member.status}</td>
                  <td className="px-2 py-2">{member.alive === true ? "Sí" : member.alive === false ? "No" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--muted)]">
            {data ? `${data.total} miembros · página ${data.page}/${data.total_pages}` : busy ? "Cargando…" : "Sin datos"}
          </span>
          <div className="flex gap-2">
            <button className="btn btn-secondary" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Anterior
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              disabled={!data || page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
