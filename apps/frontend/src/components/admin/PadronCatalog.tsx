"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Member = {
  id: string;
  registry_code: string | null;
  full_name: string;
  dni: string;
  email: string;
  status: string;
  member_type: string | null;
  membership_months: number;
  decade: number | null;
  graduation_year: number | null;
  semester: string | null;
  sex: string | null;
  alive: boolean | null;
  region: string | null;
  section: string | null;
  location: string | null;
  title: string | null;
  mention: string | null;
  graduation_date: string | null;
  region_id?: string | null;
  state_id?: string | null;
  municipality_id?: string | null;
  photo_filename: string | null;
  has_photo?: boolean;
};

type MemberList = {
  items: Member[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
};

type TerritoryUnit = { id: string; code: string; name: string; parent_id?: string | null };

type MemberFormState = {
  registry_code: string;
  full_name: string;
  dni: string;
  email: string;
  status: string;
  member_type: string;
  membership_months: string;
  decade: string;
  graduation_year: string;
  semester: string;
  sex: string;
  alive: string;
  title: string;
  mention: string;
  graduation_date: string;
  region_id: string;
  state_id: string;
  municipality_id: string;
};

type PanelMode = "preview" | "edit" | null;

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const emptyForm = (): MemberFormState => ({
  registry_code: "",
  full_name: "",
  dni: "",
  email: "",
  status: "ACTIVE",
  member_type: "",
  membership_months: "0",
  decade: "",
  graduation_year: "",
  semester: "",
  sex: "",
  alive: "",
  title: "",
  mention: "",
  graduation_date: "",
  region_id: "",
  state_id: "",
  municipality_id: "",
});

function memberToForm(member: Member): MemberFormState {
  return {
    registry_code: member.registry_code ?? "",
    full_name: member.full_name,
    dni: member.dni,
    email: member.email,
    status: member.status || "ACTIVE",
    member_type: member.member_type ?? "",
    membership_months: String(member.membership_months ?? 0),
    decade: member.decade != null ? String(member.decade) : "",
    graduation_year: member.graduation_year != null ? String(member.graduation_year) : "",
    semester: member.semester ?? "",
    sex: member.sex ?? "",
    alive: member.alive === true ? "true" : member.alive === false ? "false" : "",
    title: member.title ?? "",
    mention: member.mention ?? "",
    graduation_date: member.graduation_date ?? "",
    region_id: member.region_id ?? "",
    state_id: member.state_id ?? "",
    municipality_id: member.municipality_id ?? "",
  };
}

function formToPayload(form: MemberFormState) {
  return {
    registry_code: form.registry_code.trim() || null,
    full_name: form.full_name.trim(),
    dni: form.dni.trim(),
    email: form.email.trim(),
    status: form.status || "ACTIVE",
    member_type: form.member_type.trim() || null,
    membership_months: Number(form.membership_months) || 0,
    decade: form.decade ? Number(form.decade) : null,
    graduation_year: form.graduation_year ? Number(form.graduation_year) : null,
    semester: form.semester.trim() || null,
    sex: form.sex.trim() || null,
    alive: form.alive === "true" ? true : form.alive === "false" ? false : null,
    title: form.title.trim() || null,
    mention: form.mention.trim() || null,
    graduation_date: form.graduation_date || null,
    region_id: form.region_id || null,
    state_id: form.state_id || null,
    municipality_id: form.municipality_id || null,
  };
}

export function PadronCatalog() {
  const [query, setQuery] = useState("");
  const [regionId, setRegionId] = useState("");
  const [stateId, setStateId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [aliveFilter, setAliveFilter] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<MemberList | null>(null);
  const [regions, setRegions] = useState<TerritoryUnit[]>([]);
  const [states, setStates] = useState<TerritoryUnit[]>([]);
  const [municipalities, setMunicipalities] = useState<TerritoryUnit[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [panelMode, setPanelMode] = useState<PanelMode>(null);
  const [selected, setSelected] = useState<Member | null>(null);
  const [editForm, setEditForm] = useState<MemberFormState>(emptyForm());
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);

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
      if (statusFilter) params.set("status", statusFilter);
      if (aliveFilter === "true" || aliveFilter === "false") params.set("alive", aliveFilter);
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
  }, [page, query, regionId, stateId, statusFilter, aliveFilter]);

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
      fetch(`${apiUrl()}/api/v1/admin/territory/municipalities`, { credentials: "include" }),
    ]).then(async ([rRes, sRes, mRes]) => {
      if (rRes.ok) setRegions((await rRes.json()) as TerritoryUnit[]);
      if (sRes.ok) setStates((await sRes.json()) as TerritoryUnit[]);
      if (mRes.ok) setMunicipalities((await mRes.json()) as TerritoryUnit[]);
    });
  }, []);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    async function loadPhoto(memberId: string) {
      try {
        const response = await fetch(`${apiUrl()}/api/v1/admin/members/${memberId}/photo`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!response.ok) {
          if (!cancelled) setPhotoUrl(null);
          return;
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setPhotoUrl(objectUrl);
      } catch {
        if (!cancelled) setPhotoUrl(null);
      }
    }

    if (selected?.has_photo || selected?.photo_filename) {
      void loadPhoto(selected.id);
    } else {
      setPhotoUrl(null);
    }

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selected]);

  const filteredStates = useMemo(
    () => states.filter((s) => !regionId || s.parent_id === regionId),
    [states, regionId],
  );
  const formStates = useMemo(
    () => states.filter((s) => !form.region_id || s.parent_id === form.region_id),
    [states, form.region_id],
  );
  const formMunicipalities = useMemo(
    () => municipalities.filter((m) => !form.state_id || m.parent_id === form.state_id),
    [municipalities, form.state_id],
  );
  const editStates = useMemo(
    () => states.filter((s) => !editForm.region_id || s.parent_id === editForm.region_id),
    [states, editForm.region_id],
  );
  const editMunicipalities = useMemo(
    () => municipalities.filter((m) => !editForm.state_id || m.parent_id === editForm.state_id),
    [municipalities, editForm.state_id],
  );

  function territoryLabel(units: TerritoryUnit[], id: string | null | undefined) {
    if (!id) return "—";
    return units.find((u) => u.id === id)?.name ?? "—";
  }

  async function createMember(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formToPayload(form)),
      });
      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo crear el miembro.");
        return;
      }
      setForm(emptyForm());
      setMessage("Miembro creado correctamente.");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function openPanel(member: Member, mode: Exclude<PanelMode, null>) {
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members/${member.id}`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json()) as Member & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cargar el miembro.");
        return;
      }
      setSelected(payload);
      setEditForm(memberToForm(payload));
      setPanelMode(mode);
    } finally {
      setBusy(false);
    }
  }

  function closePanel() {
    setPanelMode(null);
    setSelected(null);
    setEditForm(emptyForm());
    setPhotoUrl(null);
  }

  async function saveMember(event: React.FormEvent) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members/${selected.id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formToPayload(editForm)),
      });
      const payload = (await response.json()) as Member & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo actualizar el miembro.");
        return;
      }
      setSelected(payload);
      setEditForm(memberToForm(payload));
      setPanelMode("preview");
      setMessage("Miembro actualizado correctamente.");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function deleteMember(member: Member) {
    const confirmed = window.confirm(
      `¿Eliminar a ${member.full_name}? Esta acción no se puede deshacer.`,
    );
    if (!confirmed) return;
    setBusy(true);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members/${member.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setMessage(payload.detail ?? "No se pudo eliminar el miembro.");
        return;
      }
      if (selected?.id === member.id) closePanel();
      setMessage("Miembro eliminado.");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto(file: File) {
    if (!selected) return;
    setPhotoBusy(true);
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${apiUrl()}/api/v1/admin/members/${selected.id}/photo`, {
        method: "POST",
        credentials: "include",
        body,
      });
      const payload = (await response.json()) as Member & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cargar la foto.");
        return;
      }
      setSelected(payload);
      setMessage("Foto actualizada.");
      await load();
    } finally {
      setPhotoBusy(false);
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

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Padrón administrativo</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Catálogo paginado con vista previa, edición, eliminación y relación territorial
            (Región / Estado / Municipio).
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
              placeholder="Nro. CIV, DNI, nombre, región…"
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
          <label className="min-w-[140px] text-sm font-bold">
            Estatus
            <select
              className="input-field mt-1"
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value);
              }}
            >
              <option value="">Todos</option>
              <option value="ACTIVE">Activo</option>
              <option value="INACTIVE">Inactivo</option>
            </select>
          </label>
          <label className="min-w-[120px] text-sm font-bold">
            Vivo
            <select
              className="input-field mt-1"
              value={aliveFilter}
              onChange={(e) => {
                setPage(1);
                setAliveFilter(e.target.value);
              }}
            >
              <option value="">Todos</option>
              <option value="true">Sí</option>
              <option value="false">No</option>
            </select>
          </label>
          <a className="btn btn-secondary" href={`${apiUrl()}/api/v1/admin/members/template`}>
            Descargar plantilla
          </a>
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
                e.target.value = "";
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
                e.target.value = "";
              }}
            />
          </label>
        </div>

        <form
          className="grid gap-3 rounded-xl border border-dashed border-[var(--line)] p-4 md:grid-cols-2 lg:grid-cols-4"
          onSubmit={(e) => void createMember(e)}
        >
          <input
            className="input-field"
            placeholder="Nombre completo"
            required
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Documento"
            required
            value={form.dni}
            onChange={(e) => setForm({ ...form, dni: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Correo"
            required
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Nro. CIV"
            value={form.registry_code}
            onChange={(e) => setForm({ ...form, registry_code: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Tipo de miembro"
            value={form.member_type}
            onChange={(e) => setForm({ ...form, member_type: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Década"
            type="number"
            value={form.decade}
            onChange={(e) => setForm({ ...form, decade: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Año de Graduación"
            type="number"
            value={form.graduation_year}
            onChange={(e) => setForm({ ...form, graduation_year: e.target.value })}
          />
          <select
            className="input-field"
            value={form.sex}
            onChange={(e) => setForm({ ...form, sex: e.target.value })}
          >
            <option value="">Sexo</option>
            <option value="M">Masculino</option>
            <option value="F">Femenino</option>
          </select>
          <select
            className="input-field"
            value={form.region_id}
            onChange={(e) =>
              setForm({
                ...form,
                region_id: e.target.value,
                state_id: "",
                municipality_id: "",
              })
            }
          >
            <option value="">Región</option>
            {regions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <select
            className="input-field"
            value={form.state_id}
            onChange={(e) =>
              setForm({
                ...form,
                state_id: e.target.value,
                municipality_id: "",
              })
            }
          >
            <option value="">Estado</option>
            {formStates.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            className="input-field"
            value={form.municipality_id}
            onChange={(e) => setForm({ ...form, municipality_id: e.target.value })}
          >
            <option value="">Municipio</option>
            {formMunicipalities.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <input
            className="input-field"
            placeholder="Título"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <input
            className="input-field"
            placeholder="Mención"
            value={form.mention}
            onChange={(e) => setForm({ ...form, mention: e.target.value })}
          />
          <button className="btn btn-primary lg:col-span-1" type="submit" disabled={busy}>
            Alta rápida
          </button>
        </form>

        {message ? (
          <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm text-[var(--primary-dark)]">
            {message}
          </p>
        ) : null}

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[var(--muted)]">
              <tr>
                <th className="px-2 py-2">Nro. CIV</th>
                <th className="px-2 py-2">Nombre</th>
                <th className="px-2 py-2">Documento</th>
                <th className="px-2 py-2">Región</th>
                <th className="px-2 py-2">Estado</th>
                <th className="px-2 py-2">Municipio</th>
                <th className="px-2 py-2">Estatus</th>
                <th className="px-2 py-2">Vivo</th>
                <th className="px-2 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((member) => (
                <tr key={member.id} className="border-b border-[var(--line)]/70">
                  <td className="px-2 py-2 font-mono text-xs">{member.registry_code ?? "—"}</td>
                  <td className="px-2 py-2 font-semibold">{member.full_name}</td>
                  <td className="px-2 py-2">{member.dni}</td>
                  <td className="px-2 py-2">
                    {territoryLabel(regions, member.region_id) !== "—"
                      ? territoryLabel(regions, member.region_id)
                      : (member.region ?? "—")}
                  </td>
                  <td className="px-2 py-2">
                    {territoryLabel(states, member.state_id) !== "—"
                      ? territoryLabel(states, member.state_id)
                      : (member.section ?? "—")}
                  </td>
                  <td className="px-2 py-2">
                    {territoryLabel(municipalities, member.municipality_id) !== "—"
                      ? territoryLabel(municipalities, member.municipality_id)
                      : (member.location ?? "—")}
                  </td>
                  <td className="px-2 py-2">{member.status}</td>
                  <td className="px-2 py-2">
                    {member.alive === true ? "Sí" : member.alive === false ? "No" : "—"}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap justify-end gap-1">
                      <button
                        type="button"
                        className="btn btn-secondary !rounded-lg !px-2.5 !py-1.5 text-xs"
                        onClick={() => void openPanel(member, "preview")}
                        disabled={busy}
                      >
                        Vista previa
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary !rounded-lg !px-2.5 !py-1.5 text-xs"
                        onClick={() => void openPanel(member, "edit")}
                        disabled={busy}
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary !rounded-lg !px-2.5 !py-1.5 text-xs text-red-700 dark:text-red-300"
                        onClick={() => void deleteMember(member)}
                        disabled={busy}
                      >
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--muted)]">
            {data
              ? `${data.total} miembros · página ${data.page}/${data.total_pages}`
              : busy
                ? "Cargando…"
                : "Sin datos"}
          </span>
          <div className="flex gap-2">
            <button
              className="btn btn-secondary"
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
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

      {panelMode && selected ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 dark:bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-labelledby="member-panel-title"
          onClick={closePanel}
        >
          <div
            className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 id="member-panel-title" className="text-lg font-semibold">
                  {panelMode === "preview" ? "Vista previa" : "Editar miembro"}
                </h3>
                <p className="text-sm text-[var(--muted)]">{selected.full_name}</p>
              </div>
              <button type="button" className="btn btn-secondary !px-3 !py-1.5" onClick={closePanel}>
                Cerrar
              </button>
            </div>

            {panelMode === "preview" ? (
              <div className="grid gap-6 md:grid-cols-[200px_1fr]">
                <div className="space-y-3">
                  <div className="flex aspect-[3/4] items-center justify-center overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--background)]">
                    {photoUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={photoUrl}
                        alt={`Foto de ${selected.full_name}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="px-3 text-center text-sm text-[var(--muted)]">
                        Sin fotografía
                      </span>
                    )}
                  </div>
                  <label className="btn btn-secondary w-full cursor-pointer !rounded-lg">
                    {photoBusy ? "Subiendo…" : "Subir foto"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="hidden"
                      disabled={photoBusy}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void uploadPhoto(file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                </div>
                <dl className="grid gap-3 sm:grid-cols-2">
                  {[
                    ["Nro. CIV", selected.registry_code ?? "—"],
                    ["Documento", selected.dni],
                    ["Correo", selected.email],
                    ["Estatus", selected.status],
                    ["Tipo", selected.member_type ?? "—"],
                    ["Membresía (meses)", String(selected.membership_months)],
                    ["Década", selected.decade != null ? String(selected.decade) : "—"],
                    [
                      "Año de Graduación",
                      selected.graduation_year != null ? String(selected.graduation_year) : "—",
                    ],
                    ["Semestre", selected.semester ?? "—"],
                    [
                      "Sexo",
                      selected.sex === "M"
                        ? "Masculino"
                        : selected.sex === "F"
                          ? "Femenino"
                          : (selected.sex ?? "—"),
                    ],
                    [
                      "Vivo",
                      selected.alive === true ? "Sí" : selected.alive === false ? "No" : "—",
                    ],
                    [
                      "Región",
                      territoryLabel(regions, selected.region_id) !== "—"
                        ? territoryLabel(regions, selected.region_id)
                        : (selected.region ?? "—"),
                    ],
                    [
                      "Estado",
                      territoryLabel(states, selected.state_id) !== "—"
                        ? territoryLabel(states, selected.state_id)
                        : (selected.section ?? "—"),
                    ],
                    [
                      "Municipio",
                      territoryLabel(municipalities, selected.municipality_id) !== "—"
                        ? territoryLabel(municipalities, selected.municipality_id)
                        : (selected.location ?? "—"),
                    ],
                    ["Título", selected.title ?? "—"],
                    ["Mención", selected.mention ?? "—"],
                    ["Fecha grado", selected.graduation_date ?? "—"],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-[var(--line)] px-3 py-2">
                      <dt className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                        {label}
                      </dt>
                      <dd className="mt-1 text-sm font-medium">{value}</dd>
                    </div>
                  ))}
                </dl>
                <div className="flex flex-wrap gap-2 md:col-span-2">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setPanelMode("edit")}
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary text-red-700 dark:text-red-300"
                    onClick={() => void deleteMember(selected)}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            ) : (
              <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => void saveMember(e)}>
                <div className="space-y-3 md:row-span-6">
                  <div className="flex aspect-[3/4] max-h-72 items-center justify-center overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--background)]">
                    {photoUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={photoUrl}
                        alt={`Foto de ${selected.full_name}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="px-3 text-center text-sm text-[var(--muted)]">
                        Sin fotografía
                      </span>
                    )}
                  </div>
                  <label className="btn btn-secondary w-full cursor-pointer !rounded-lg">
                    {photoBusy ? "Subiendo…" : "Subir foto"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="hidden"
                      disabled={photoBusy}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void uploadPhoto(file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                </div>
                <label className="text-sm font-bold">
                  Nombre completo
                  <input
                    className="input-field mt-1"
                    required
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Documento
                  <input
                    className="input-field mt-1"
                    required
                    value={editForm.dni}
                    onChange={(e) => setEditForm({ ...editForm, dni: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Correo
                  <input
                    className="input-field mt-1"
                    required
                    type="email"
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Estatus
                  <select
                    className="input-field mt-1"
                    value={editForm.status}
                    onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                  >
                    <option value="ACTIVE">Activo</option>
                    <option value="INACTIVE">Inactivo</option>
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Vivo
                  <select
                    className="input-field mt-1"
                    value={editForm.alive}
                    onChange={(e) => setEditForm({ ...editForm, alive: e.target.value })}
                  >
                    <option value="">Sin definir</option>
                    <option value="true">Sí</option>
                    <option value="false">No</option>
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Nro. CIV
                  <input
                    className="input-field mt-1"
                    value={editForm.registry_code}
                    onChange={(e) => setEditForm({ ...editForm, registry_code: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Tipo de miembro
                  <input
                    className="input-field mt-1"
                    value={editForm.member_type}
                    onChange={(e) => setEditForm({ ...editForm, member_type: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Década
                  <input
                    className="input-field mt-1"
                    type="number"
                    min={0}
                    value={editForm.decade}
                    onChange={(e) => setEditForm({ ...editForm, decade: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Año de Graduación
                  <input
                    className="input-field mt-1"
                    type="number"
                    min={1900}
                    max={2100}
                    value={editForm.graduation_year}
                    onChange={(e) =>
                      setEditForm({ ...editForm, graduation_year: e.target.value })
                    }
                  />
                </label>
                <label className="text-sm font-bold">
                  Sexo
                  <select
                    className="input-field mt-1"
                    value={editForm.sex}
                    onChange={(e) => setEditForm({ ...editForm, sex: e.target.value })}
                  >
                    <option value="">Sin definir</option>
                    <option value="M">Masculino</option>
                    <option value="F">Femenino</option>
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Membresía (meses)
                  <input
                    className="input-field mt-1"
                    type="number"
                    min={0}
                    value={editForm.membership_months}
                    onChange={(e) =>
                      setEditForm({ ...editForm, membership_months: e.target.value })
                    }
                  />
                </label>
                <label className="text-sm font-bold">
                  Región
                  <select
                    className="input-field mt-1"
                    value={editForm.region_id}
                    onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        region_id: e.target.value,
                        state_id: "",
                        municipality_id: "",
                      })
                    }
                  >
                    <option value="">Seleccione región</option>
                    {regions.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Estado
                  <select
                    className="input-field mt-1"
                    value={editForm.state_id}
                    onChange={(e) =>
                      setEditForm({
                        ...editForm,
                        state_id: e.target.value,
                        municipality_id: "",
                      })
                    }
                  >
                    <option value="">Seleccione estado</option>
                    {editStates.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Municipio
                  <select
                    className="input-field mt-1"
                    value={editForm.municipality_id}
                    onChange={(e) =>
                      setEditForm({ ...editForm, municipality_id: e.target.value })
                    }
                  >
                    <option value="">Seleccione municipio</option>
                    {editMunicipalities.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-bold">
                  Título
                  <input
                    className="input-field mt-1"
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Mención
                  <input
                    className="input-field mt-1"
                    value={editForm.mention}
                    onChange={(e) => setEditForm({ ...editForm, mention: e.target.value })}
                  />
                </label>
                <label className="text-sm font-bold">
                  Fecha de grado
                  <input
                    className="input-field mt-1"
                    type="date"
                    value={editForm.graduation_date}
                    onChange={(e) => setEditForm({ ...editForm, graduation_date: e.target.value })}
                  />
                </label>
                <div className="flex flex-wrap gap-2 md:col-span-2">
                  <button className="btn btn-primary" type="submit" disabled={busy}>
                    Guardar cambios
                  </button>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setPanelMode("preview")}
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      ) : null}
    </DashboardShell>
  );
}
