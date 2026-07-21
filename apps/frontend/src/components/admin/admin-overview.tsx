"use client";

import { useEffect, useState } from "react";


type AdminOverview = {
  organization_slug: string;
  organization_name: string;
  roles: string[];
  member_count: number;
  election_count: number;
  encrypted_ballot_count: number;
};

export function AdminOverview() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [message, setMessage] = useState("Cargando resumen administrativo…");

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    async function loadOverview() {
      try {
        const response = await fetch(`${apiUrl}/api/v1/admin/overview`, {
          credentials: "include",
          cache: "no-store",
        });
        const payload = (await response.json()) as AdminOverview & { detail?: string };
        if (!response.ok) {
          setMessage(
            response.status === 401
              ? "Tu sesión administrativa no está activa. Accede para continuar."
              : payload.detail ?? "No se pudo cargar el resumen administrativo.",
          );
          return;
        }
        setOverview(payload);
        setMessage("");
      } catch {
        setMessage("No se pudo contactar la API administrativa.");
      }
    }

    void loadOverview();
  }, []);

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
    </>
  );
}
