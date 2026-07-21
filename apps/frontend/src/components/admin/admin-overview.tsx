"use client";

import { useEffect, useState, type FormEvent } from "react";

type AdminOverview = {
  organization_slug: string;
  organization_name: string;
  roles: string[];
  member_count: number;
  election_count: number;
  encrypted_ballot_count: number;
};

type AdminElection = {
  id: string;
  title: string;
  voting_type: string;
  start_time: string;
  end_time: string;
  quorum_threshold_pct: string;
  status: string;
  created_at: string;
};

type AdminPosition = {
  id: string;
  election_id: string;
  title: string;
  code: string;
  is_required: boolean;
  display_order: number;
  created_at: string;
};

type ApiError = { detail?: string };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function AdminOverview() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [selectedElection, setSelectedElection] = useState<AdminElection | null>(null);
  const [positions, setPositions] = useState<AdminPosition[]>([]);
  const [message, setMessage] = useState("Cargando resumen administrativo…");
  const [positionMessage, setPositionMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [positionBusy, setPositionBusy] = useState(false);

  async function loadData() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const [overviewResponse, electionsResponse] = await Promise.all([
      fetch(`${apiUrl}/api/v1/admin/overview`, {
        credentials: "include",
        cache: "no-store",
      }),
      fetch(`${apiUrl}/api/v1/admin/elections`, {
        credentials: "include",
        cache: "no-store",
      }),
    ]);
    const overviewPayload = (await overviewResponse.json()) as AdminOverview & ApiError;
    const electionsPayload = (await electionsResponse.json()) as AdminElection[] & ApiError;

    if (!overviewResponse.ok || !electionsResponse.ok) {
      const unauthorized = overviewResponse.status === 401 || electionsResponse.status === 401;
      throw new Error(
        unauthorized
          ? "Tu sesión administrativa no está activa. Accede para continuar."
          : overviewPayload.detail ?? electionsPayload.detail ?? "No se pudo cargar el resumen administrativo.",
      );
    }
    setOverview(overviewPayload);
    setElections(electionsPayload);
    setMessage("");
  }

  useEffect(() => {
    void loadData().catch((error: unknown) => {
      setMessage(error instanceof Error ? error.message : "No se pudo cargar el resumen administrativo.");
    });
  }, []);

  async function handleCreateElection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const startTime = String(form.get("start_time") ?? "");
    const endTime = String(form.get("end_time") ?? "");
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/elections`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: String(form.get("title") ?? "").trim(),
          voting_type: "SLATE_PLURALITY",
          start_time: new Date(startTime).toISOString(),
          end_time: new Date(endTime).toISOString(),
          quorum_threshold_pct: Number(form.get("quorum_threshold_pct") ?? 30),
        }),
      });
      const payload = (await response.json()) as AdminElection & ApiError;
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo crear la elección.");
        return;
      }
      setElections((current) => [...current, payload].sort((left, right) =>
        new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
      ));
      setOverview((current) =>
        current ? { ...current, election_count: current.election_count + 1 } : current,
      );
      event.currentTarget.reset();
      setMessage("Elección creada en estado DRAFT.");
    } catch {
      setMessage("No se pudo contactar la API administrativa.");
    } finally {
      setBusy(false);
    }
  }

  async function loadPositions(election: AdminElection) {
    setSelectedElection(election);
    setPositionMessage(null);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const response = await fetch(`${apiUrl}/api/v1/admin/elections/${election.id}/positions`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json()) as AdminPosition[] & ApiError;
      if (!response.ok) {
        setPositionMessage(payload.detail ?? "No se pudieron cargar las posiciones.");
        setPositions([]);
        return;
      }
      setPositions(payload);
    } catch {
      setPositionMessage("No se pudo contactar la API administrativa.");
    }
  }

  async function handleCreatePosition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedElection) return;
    setPositionBusy(true);
    setPositionMessage(null);
    const form = new FormData(event.currentTarget);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    try {
      const response = await fetch(
        `${apiUrl}/api/v1/admin/elections/${selectedElection.id}/positions`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: String(form.get("position_title") ?? "").trim(),
            code: String(form.get("position_code") ?? "").trim(),
            is_required: form.get("position_required") === "on",
            display_order: Number(form.get("position_order") ?? 0),
          }),
        },
      );
      const payload = (await response.json()) as AdminPosition & ApiError;
      if (!response.ok) {
        setPositionMessage(payload.detail ?? "No se pudo crear la posición.");
        return;
      }
      setPositions((current) => [...current, payload].sort(
        (left, right) => left.display_order - right.display_order,
      ));
      event.currentTarget.reset();
      setPositionMessage("Posición creada correctamente.");
    } catch {
      setPositionMessage("No se pudo contactar la API administrativa.");
    } finally {
      setPositionBusy(false);
    }
  }

  if (!overview) {
    return <div className="notice"><p>{message}</p></div>;
  }

  return (
    <>
      <div className="notice">
        <strong>{overview.organization_name}</strong>
        <p>Organización: {overview.organization_slug}</p>
        <p>Roles activos: {overview.roles.join(", ")}</p>
      </div>
      <div className="surface-grid" aria-label="Resumen administrativo">
        <div className="surface-card">
          <span className="eyebrow">Padrón</span>
          <h2>{overview.member_count}</h2>
          <p>Miembros registrados</p>
        </div>
        <div className="surface-card">
          <span className="eyebrow">Elecciones</span>
          <h2>{overview.election_count}</h2>
          <p>Procesos de la organización</p>
        </div>
        <div className="surface-card">
          <span className="eyebrow">Urna</span>
          <h2>{overview.encrypted_ballot_count}</h2>
          <p>Papeletas cifradas</p>
        </div>
      </div>
      <section className="empty-state" aria-labelledby="election-form-title">
        <span className="eyebrow">Gestión electoral</span>
        <h2 id="election-form-title">Crear elección</h2>
        <p>Las nuevas elecciones se crean como DRAFT y permanecen aisladas a esta organización.</p>
        <form className="auth-form" onSubmit={handleCreateElection}>
          <label htmlFor="election-title">Título</label>
          <input id="election-title" name="title" minLength={3} maxLength={255} required />
          <label htmlFor="election-start">Inicio</label>
          <input id="election-start" name="start_time" type="datetime-local" required />
          <label htmlFor="election-end">Fin</label>
          <input id="election-end" name="end_time" type="datetime-local" required />
          <label htmlFor="election-quorum">Quórum (%)</label>
          <input
            id="election-quorum"
            name="quorum_threshold_pct"
            type="number"
            min="0"
            max="100"
            step="0.01"
            defaultValue="30"
            required
          />
          <button className="button button-primary" type="submit" disabled={busy}>
            {busy ? "Creando…" : "Crear elección DRAFT"}
          </button>
        </form>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </section>
      <section aria-labelledby="election-list-title">
        <span className="eyebrow">Procesos registrados</span>
        <h2 id="election-list-title">Elecciones</h2>
        {elections.length === 0 ? (
          <div className="empty-state"><p>No hay elecciones creadas para esta organización.</p></div>
        ) : (
          <div className="election-list">
            {elections.map((election) => (
              <article className="election-item" key={election.id}>
                <div>
                  <h3>{election.title}</h3>
                  <p>{election.voting_type} · Quórum {election.quorum_threshold_pct}%</p>
                </div>
                <div>
                  <time dateTime={election.start_time}>
                    {election.status} · {formatDate(election.start_time)}
                  </time>
                  <button
                    className="button button-secondary inline-button"
                    type="button"
                    onClick={() => void loadPositions(election)}
                  >
                    Configurar posiciones
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      {selectedElection ? (
        <section className="empty-state" aria-labelledby="position-title">
          <span className="eyebrow">Estructura de elección DRAFT</span>
          <h2 id="position-title">Posiciones: {selectedElection.title}</h2>
          <p>Las posiciones definen los cargos antes de registrar planchas y candidatos.</p>
          <div className="election-list">
            {positions.length === 0 ? (
              <p>No hay posiciones configuradas.</p>
            ) : positions.map((position) => (
              <article className="election-item" key={position.id}>
                <div>
                  <h3>{position.title}</h3>
                  <p>{position.code} · {position.is_required ? "Obligatoria" : "Opcional"}</p>
                </div>
                <time>Orden {position.display_order}</time>
              </article>
            ))}
          </div>
          <form className="auth-form" onSubmit={handleCreatePosition}>
            <label htmlFor="position-title-input">Título de posición</label>
            <input id="position-title-input" name="position_title" minLength={2} maxLength={100} required />
            <label htmlFor="position-code-input">Código</label>
            <input
              id="position-code-input"
              name="position_code"
              pattern="[A-Za-z][A-Za-z0-9_-]{1,49}"
              placeholder="PRESIDENTE"
              maxLength={50}
              required
            />
            <label htmlFor="position-order-input">Orden</label>
            <input
              id="position-order-input"
              name="position_order"
              type="number"
              min="0"
              max="10000"
              defaultValue="0"
              required
            />
            <label>
              <input name="position_required" type="checkbox" defaultChecked /> Posición obligatoria
            </label>
            <button className="button button-primary" type="submit" disabled={positionBusy}>
              {positionBusy ? "Creando…" : "Agregar posición"}
            </button>
          </form>
          {positionMessage ? <p className="form-message" role="status">{positionMessage}</p> : null}
        </section>
      ) : null}
    </>
  );
}
