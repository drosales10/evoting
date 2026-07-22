"use client";

import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Election = { id: string; title: string; status: string };
type AuditEvent = {
  id: string;
  event_type: string;
  created_at: string;
  actor_hash?: string | null;
  details?: Record<string, unknown> | null;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AdminAuditPage() {
  const [elections, setElections] = useState<Election[]>([]);
  const [electionId, setElectionId] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl()}/api/v1/admin/elections`, { credentials: "include", cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) return;
        const list = (await r.json()) as Election[];
        setElections(list);
        if (list[0]) setElectionId(list[0].id);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!electionId) return;
    void fetch(`${apiUrl()}/api/v1/admin/elections/${electionId}/audit`, {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (r) => {
        if (!r.ok) {
          setMessage("No se pudo cargar la auditoría de esta elección.");
          setEvents([]);
          return;
        }
        setEvents((await r.json()) as AuditEvent[]);
        setMessage(null);
      })
      .catch(() => setMessage("Error de red al cargar auditoría."));
  }, [electionId]);

  return (
    <DashboardShell>
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Auditoría</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Eventos por elección (sin PII). Exporta el CSV firmado cuando lo necesites.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[240px] flex-1 text-sm font-bold">
            Elección
            <select
              className="input-field mt-1"
              value={electionId}
              onChange={(e) => setElectionId(e.target.value)}
            >
              <option value="">Seleccionar…</option>
              {elections.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title} ({e.status})
                </option>
              ))}
            </select>
          </label>
          {electionId ? (
            <a
              className="btn btn-secondary"
              href={`${apiUrl()}/api/v1/admin/elections/${electionId}/audit/export`}
            >
              Exportar
            </a>
          ) : null}
        </div>
        {message ? <p className="text-sm text-red-600">{message}</p> : null}
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--line)] text-[var(--muted)]">
              <tr>
                <th className="px-2 py-2">Fecha</th>
                <th className="px-2 py-2">Evento</th>
                <th className="px-2 py-2">Actor hash</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id} className="border-b border-[var(--line)]/70">
                  <td className="px-2 py-2 whitespace-nowrap">
                    {new Date(event.created_at).toLocaleString("es-CO")}
                  </td>
                  <td className="px-2 py-2 font-semibold">{event.event_type}</td>
                  <td className="px-2 py-2 font-mono text-xs">{event.actor_hash ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {electionId && events.length === 0 && !message ? (
            <p className="mt-3 text-sm text-[var(--muted)]">Sin eventos para esta elección.</p>
          ) : null}
        </div>
      </div>
    </DashboardShell>
  );
}
