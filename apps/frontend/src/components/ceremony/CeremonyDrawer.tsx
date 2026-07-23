"use client";

import { useEffect, useState } from "react";

import {
  CeremonyPlayer,
  statusLabel,
  type CeremonyBroadcast,
} from "@/components/ceremony/CeremonyPlayer";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function CeremonyDrawer({ electionId }: { electionId: string }) {
  const [open, setOpen] = useState(false);
  const [broadcast, setBroadcast] = useState<CeremonyBroadcast | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!electionId) {
      setBroadcast(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetch(`${apiUrl()}/api/v1/public/elections/${electionId}/broadcast`, {
      cache: "no-store",
    })
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 404) {
          setBroadcast(null);
          setError(null);
          return;
        }
        if (!response.ok) {
          setBroadcast(null);
          setError("No se pudo cargar la ceremonia.");
          return;
        }
        setBroadcast((await response.json()) as CeremonyBroadcast);
        setError(null);
      })
      .catch(() => {
        if (!cancelled) {
          setBroadcast(null);
          setError("Error de red al cargar la ceremonia.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [electionId]);

  if (!electionId) return null;

  const live = broadcast?.status === "LIVE";
  const label = loading
    ? "Ceremonia…"
    : live
      ? "Ceremonia · En vivo"
      : broadcast
        ? `Ceremonia · ${statusLabel(broadcast.status)}`
        : "Ceremonia";

  return (
    <>
      <button
        type="button"
        className={live ? "btn btn-primary" : "btn btn-secondary"}
        onClick={() => setOpen(true)}
      >
        {label}
      </button>
      {open ? (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/45 dark:bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-labelledby="ceremony-drawer-title"
          onClick={() => setOpen(false)}
        >
          <aside
            className="flex h-full w-full max-w-lg flex-col border-l border-[var(--line)] bg-[var(--surface)] shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
              <h2 id="ceremony-drawer-title" className="text-lg font-semibold">
                Ceremonia
              </h2>
              <button
                type="button"
                className="btn btn-secondary !px-3 !py-1.5"
                onClick={() => setOpen(false)}
              >
                Cerrar
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {error ? <p className="text-sm text-amber-400">{error}</p> : null}
              {broadcast ? (
                <CeremonyPlayer broadcast={broadcast} />
              ) : (
                <div className="space-y-3 text-sm text-[var(--muted)]">
                  <p className="font-semibold text-[var(--ink)]">Sin live anunciado</p>
                  <p>
                    La comisión aún no publicó una transmisión YouTube para esta elección. Cuando
                    lo haga, podrás seguir aquí el cierre, la comparación de claves y la
                    publicación de resultados.
                  </p>
                  <a className="btn btn-secondary inline-flex" href="/cliente/ceremonia">
                    Ir a Ceremonia
                  </a>
                </div>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
