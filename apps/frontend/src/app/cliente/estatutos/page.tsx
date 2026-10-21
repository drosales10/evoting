"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type PublicStatute = {
  id: string;
  title: string;
  status: string;
  end_time: string;
  has_results: boolean;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATUS_LABEL: Record<string, string> = {
  ACTIVE: "En votación",
  CLOSED: "Cerrada",
  TALLIED: "Acta publicada",
};

export default function ClienteEstatutosPage() {
  const [items, setItems] = useState<PublicStatute[] | null>(null);

  useEffect(() => {
    void fetch(`${apiUrl}/api/v1/public/statutes`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          setItems([]);
          return;
        }
        setItems((await response.json()) as PublicStatute[]);
      })
      .catch(() => setItems([]));
  }, []);

  return (
    <div className="space-y-6 text-[var(--ink)]">
      <div>
        <h1 className="text-3xl font-semibold">Estatutos</h1>
        <p className="mt-1 text-[var(--muted)]">
          Texto de las consultas abiertas o ya escrutadas. Las respuestas con nombre aparecen cuando hay acta.
        </p>
      </div>
      {items === null ? <p className="text-sm text-[var(--muted)]">Cargando…</p> : null}
      {items?.length === 0 ? (
        <p className="card-panel text-sm text-[var(--muted)]">No hay consultas de estatutos publicadas.</p>
      ) : null}
      <div className="space-y-3">
        {items?.map((item) => (
          <Link
            key={item.id}
            href={`/cliente/estatutos/${item.id}`}
            className="card-panel flex flex-wrap items-center justify-between gap-3"
          >
            <div>
              <p className="font-semibold">{item.title}</p>
              <p className="text-sm text-[var(--muted)]">{STATUS_LABEL[item.status] ?? item.status}</p>
            </div>
            <span className="text-sm font-bold text-[var(--primary)]">Ver texto</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
