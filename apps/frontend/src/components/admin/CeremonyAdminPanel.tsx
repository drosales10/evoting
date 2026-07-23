"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  CeremonyPlayer,
  statusLabel,
  type CeremonyBroadcast,
} from "@/components/ceremony/CeremonyPlayer";

type AdminBroadcast = CeremonyBroadcast & {
  id: string;
  has_key_compare_milestone: boolean;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function csrfHeaders(): HeadersInit {
  const csrfToken = window.sessionStorage.getItem("evoting_admin_csrf");
  if (!csrfToken) throw new Error("Sesión ADMIN sin CSRF. Inicia sesión nuevamente.");
  return {
    "Content-Type": "application/json",
    "X-CSRF-Token": csrfToken,
  };
}

function StatusBadge({ status }: { status: string }) {
  const live = status === "LIVE";
  return (
    <span
      className={
        live
          ? "inline-flex items-center gap-1.5 rounded-full bg-red-600/15 px-2.5 py-1 text-xs font-bold text-red-700 dark:text-red-300"
          : "inline-flex items-center rounded-full border border-[var(--line)] bg-[var(--background)] px-2.5 py-1 text-xs font-bold text-[var(--muted)]"
      }
    >
      {live ? <span className="size-1.5 animate-pulse rounded-full bg-red-600" /> : null}
      {statusLabel(status)}
    </span>
  );
}

export function CeremonyAdminPanel({
  electionId,
  electionTitle,
}: {
  electionId: string;
  electionTitle?: string;
}) {
  const [broadcast, setBroadcast] = useState<AdminBroadcast | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    youtube_url: "",
    title: "Ceremonia de escrutinio",
    description: "",
    scheduled_start_at: "",
  });

  const load = useCallback(async () => {
    const response = await fetch(
      `${apiUrl()}/api/v1/admin/elections/${electionId}/broadcast`,
      { credentials: "include", cache: "no-store" },
    );
    if (response.status === 404) {
      setBroadcast(null);
      setForm({
        youtube_url: "",
        title: electionTitle
          ? `Ceremonia · ${electionTitle}`
          : "Ceremonia de escrutinio",
        description: "",
        scheduled_start_at: "",
      });
      return;
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      setMessage(payload.detail ?? "No se pudo cargar la transmisión.");
      return;
    }
    const data = (await response.json()) as AdminBroadcast;
    setBroadcast(data);
    setForm({
      youtube_url: data.youtube_url,
      title: data.title,
      description: data.description ?? "",
      scheduled_start_at: data.scheduled_start_at
        ? data.scheduled_start_at.slice(0, 16)
        : "",
    });
  }, [electionId, electionTitle]);

  useEffect(() => {
    void load().catch(() => setMessage("Error de red al cargar la transmisión."));
  }, [load]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${apiUrl()}/api/v1/admin/elections/${electionId}/broadcast`,
        {
          method: "PUT",
          credentials: "include",
          headers: csrfHeaders(),
          body: JSON.stringify({
            youtube_url: form.youtube_url,
            title: form.title,
            description: form.description || null,
            scheduled_start_at: form.scheduled_start_at
              ? new Date(form.scheduled_start_at).toISOString()
              : null,
          }),
        },
      );
      const payload = (await response.json()) as AdminBroadcast & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo guardar la transmisión.");
        return;
      }
      setBroadcast(payload);
      setMessage("Transmisión guardada. Ya es visible en el portal cliente (drawer Ceremonia).");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Error al guardar.");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(status: string) {
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${apiUrl()}/api/v1/admin/elections/${electionId}/broadcast/status`,
        {
          method: "POST",
          credentials: "include",
          headers: csrfHeaders(),
          body: JSON.stringify({ status }),
        },
      );
      const payload = (await response.json()) as AdminBroadcast & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cambiar el estado.");
        return;
      }
      setBroadcast(payload);
      setMessage(`Estado actualizado: ${statusLabel(status)}.`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Error de red.");
    } finally {
      setBusy(false);
    }
  }

  async function addMilestone(type: string) {
    setBusy(true);
    setMessage(null);
    try {
      const response = await fetch(
        `${apiUrl()}/api/v1/admin/elections/${electionId}/broadcast/milestones`,
        {
          method: "POST",
          credentials: "include",
          headers: csrfHeaders(),
          body: JSON.stringify({ type }),
        },
      );
      const payload = (await response.json()) as AdminBroadcast & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo registrar el hito.");
        return;
      }
      setBroadcast(payload);
      setMessage("Hito registrado en la timeline pública.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Error de red.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
            Evidencia audiovisual
          </p>
          <h3 className="mt-1 text-lg font-semibold">
            {electionTitle ? `Live · ${electionTitle}` : "Ceremonia de escrutinio"}
          </h3>
          <p className="mt-1 max-w-2xl text-sm text-[var(--muted)]">
            Un solo live por elección: cierre, comparación de claves (offline) y publicación.
            El público lo ve en el drawer <strong>Ceremonia</strong> del geovisor cliente.
          </p>
        </div>
        {broadcast ? <StatusBadge status={broadcast.status} /> : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <form
          className="space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--background)] p-4"
          onSubmit={(e) => void save(e)}
        >
          <p className="text-sm font-bold">1. Configurar transmisión</p>
          <label className="block text-sm font-bold">
            URL de YouTube
            <input
              className="input-field mt-1"
              placeholder="https://www.youtube.com/live/… o /watch?v=…"
              required
              value={form.youtube_url}
              onChange={(e) => setForm({ ...form, youtube_url: e.target.value })}
            />
          </label>
          <label className="block text-sm font-bold">
            Título público
            <input
              className="input-field mt-1"
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </label>
          <label className="block text-sm font-bold">
            Inicio programado
            <input
              className="input-field mt-1"
              type="datetime-local"
              value={form.scheduled_start_at}
              onChange={(e) => setForm({ ...form, scheduled_start_at: e.target.value })}
            />
          </label>
          <label className="block text-sm font-bold">
            Descripción
            <textarea
              className="input-field mt-1"
              rows={3}
              placeholder="Qué verá el público durante la ceremonia"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {broadcast ? "Guardar cambios" : "Anunciar live"}
          </button>
        </form>

        <div className="space-y-3 rounded-2xl border border-[var(--line)] bg-[var(--background)] p-4">
          <p className="text-sm font-bold">2. Controlar el live y los hitos</p>
          {!broadcast ? (
            <p className="text-sm text-[var(--muted)]">
              Primero anuncia la URL de YouTube. Luego podrás marcar en vivo y registrar hitos.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-primary !px-3 !py-2 text-xs"
                  disabled={busy || broadcast.status === "LIVE"}
                  onClick={() => void setStatus("LIVE")}
                >
                  Marcar en vivo
                </button>
                <button
                  type="button"
                  className="btn btn-secondary !px-3 !py-2 text-xs"
                  disabled={busy}
                  onClick={() => void setStatus("ENDED")}
                >
                  Finalizar
                </button>
                <button
                  type="button"
                  className="btn btn-secondary !px-3 !py-2 text-xs"
                  disabled={busy}
                  onClick={() => void setStatus("ARCHIVED")}
                >
                  Archivar VOD
                </button>
              </div>
              <div className="border-t border-[var(--line)] pt-3">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                  Hitos del mismo live
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn btn-secondary !px-3 !py-2 text-xs"
                    disabled={busy}
                    onClick={() => void addMilestone("CLOSE")}
                  >
                    Cierre de votación
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary !px-3 !py-2 text-xs"
                    disabled={busy}
                    onClick={() => void addMilestone("KEY_COMPARE")}
                  >
                    Comparación de claves
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary !px-3 !py-2 text-xs"
                    disabled={busy}
                    onClick={() => void addMilestone("PUBLISH")}
                  >
                    Publicación
                  </button>
                </div>
              </div>
              {!broadcast.has_key_compare_milestone ? (
                <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm text-[var(--primary-dark)]">
                  Advertencia: falta el hito de comparación de claves (proceso offline). Al
                  publicar el tally se pedirá confirmación, pero no se bloquea.
                </p>
              ) : (
                <p className="text-sm text-[var(--muted)]">
                  Hito de comparación de claves registrado.
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {message ? (
        <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-sm text-[var(--primary-dark)]">
          {message}
        </p>
      ) : null}

      {broadcast ? (
        <div className="rounded-2xl border border-[var(--line)] p-4">
          <p className="mb-3 text-sm font-bold">Vista previa (igual que verá el público)</p>
          <CeremonyPlayer broadcast={broadcast} />
        </div>
      ) : null}
    </div>
  );
}
