"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";

type Election = {
  id: string;
  title: string;
  status: string;
  start_time: string;
  end_time: string;
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function AdminResultadosPage() {
  const [elections, setElections] = useState<Election[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl()}/api/v1/admin/elections`, {
      credentials: "include",
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          setError("No se pudieron cargar las elecciones.");
          return;
        }
        const list = (await response.json()) as Election[];
        setElections(list.filter((e) => e.status === "TALLIED" || e.status === "CLOSED"));
      })
      .catch(() => setError("Error de red al cargar elecciones."));
  }, []);

  const tallied = elections.filter((e) => e.status === "TALLIED");

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">Resultados electorales</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Tablero de participación, plancha ganadora y mapa espacial (incluye tallies piloto).
          </p>
        </div>

        {error ? <p className="text-sm text-red-600 dark:text-amber-300">{error}</p> : null}

        {tallied.length === 0 && !error ? (
          <div className="card-panel">
            <p className="text-sm text-[var(--muted)]">
              Aún no hay elecciones en estado TALLIED. Publica el escrutinio desde Elecciones.
            </p>
            <Link className="btn btn-secondary mt-3" href="/admin/elections">
              Ir a elecciones
            </Link>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {tallied.map((election) => (
              <Link
                key={election.id}
                href={`/admin/resultados/${election.id}`}
                className="card-panel transition hover:border-[var(--primary)]"
              >
                <p className="eyebrow">{election.status}</p>
                <p className="mt-2 text-lg font-semibold">{election.title}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  Ver dashboard · geovisor de participación
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
