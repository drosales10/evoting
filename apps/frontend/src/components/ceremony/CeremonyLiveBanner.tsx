"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  CeremonyPlayer,
  statusLabel,
  type CeremonyBroadcast,
} from "@/components/ceremony/CeremonyPlayer";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ElectionSummary = {
  id: string;
  title: string;
  status: string;
  has_live?: boolean;
  broadcast_status?: string | null;
};

export function CeremonyLiveBanner({
  electionId,
  compact = false,
}: {
  electionId?: string;
  compact?: boolean;
}) {
  const [items, setItems] = useState<
    Array<{ election: ElectionSummary; broadcast: CeremonyBroadcast }>
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const electionsRes = await fetch(`${apiUrl()}/api/v1/public/elections`, {
          cache: "no-store",
        });
        if (!electionsRes.ok) {
          if (!cancelled) setItems([]);
          return;
        }
        let elections = (await electionsRes.json()) as ElectionSummary[];
        if (electionId) {
          elections = elections.filter((e) => e.id === electionId);
        } else {
          elections = elections.filter((e) => Boolean(e.broadcast_status));
        }

        const paired = await Promise.all(
          elections.map(async (election) => {
            const response = await fetch(
              `${apiUrl()}/api/v1/public/elections/${election.id}/broadcast`,
              { cache: "no-store" },
            );
            if (!response.ok) return null;
            const broadcast = (await response.json()) as CeremonyBroadcast;
            return { election, broadcast };
          }),
        );
        if (!cancelled) {
          setItems(paired.filter((item): item is NonNullable<typeof item> => item !== null));
        }
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [electionId]);

  if (loading) {
    return (
      <p className="text-sm text-[var(--muted)]">
        {compact ? "Buscando ceremonia…" : "Cargando ceremonias anunciadas…"}
      </p>
    );
  }

  if (items.length === 0) {
    if (compact) return null;
    return (
      <section className="rounded-2xl border border-dashed border-[var(--line)] bg-[var(--surface)] p-5">
        <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
          Ceremonia YouTube
        </p>
        <h2 className="mt-2 text-xl font-semibold">Aún no hay live anunciado</h2>
        <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
          Cuando la comisión publique la transmisión del escrutinio, aparecerá aquí y en el
          geovisor (drawer Ceremonia) para que cualquiera pueda seguir el cierre, la comparación
          de claves y la activación de resultados.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-4">
      {items.map(({ election, broadcast }) => (
        <section
          key={election.id}
          className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--surface)]"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] px-5 py-4">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
                Ceremonia YouTube · {statusLabel(broadcast.status)}
              </p>
              <h2 className="mt-1 text-xl font-semibold">{broadcast.title}</h2>
              <p className="text-sm text-[var(--muted)]">{election.title}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {broadcast.status === "LIVE" ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-red-600/20 px-3 py-1 text-xs font-bold text-red-300">
                  <span className="size-1.5 animate-pulse rounded-full bg-red-500" />
                  En vivo
                </span>
              ) : null}
              <Link className="btn btn-secondary !px-3 !py-2 text-xs" href="/cliente/geovisor">
                Ver en geovisor
              </Link>
              <Link
                className="btn btn-primary !px-3 !py-2 text-xs"
                href={`/cliente/ceremonia?election=${election.id}`}
              >
                Abrir ceremonia
              </Link>
            </div>
          </div>
          {!compact ? (
            <div className="p-5">
              <CeremonyPlayer broadcast={broadcast} />
            </div>
          ) : (
            <div className="px-5 py-4 text-sm text-[var(--muted)]">
              {broadcast.description ||
                "Sigue el cierre del escrutinio y la activación de resultados en el live oficial."}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
