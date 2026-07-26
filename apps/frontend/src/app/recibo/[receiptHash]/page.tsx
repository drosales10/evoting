"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { APP_TIMEZONE, formatAppDateTime } from "@/lib/datetime";
import { formatApiError } from "@/lib/api-error";
import { notify } from "@/lib/notify";

type PublicReceiptPayload = {
  exists: boolean;
  receipt_hash: string;
  ballot_id: string;
  election_id: string;
  election_title: string;
  election_status: string;
  recorded_at: string;
  qr_payload: string;
  status: string;
  detail?: string;
};

export default function PublicReciboPage() {
  const params = useParams<{ receiptHash: string }>();
  const [data, setData] = useState<PublicReceiptPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const hash = params.receiptHash?.trim().toLowerCase();
    if (!hash) {
      setLoading(false);
      const text = "Hash de recibo no válido.";
      setError(text);
      notify.error(text);
      return;
    }
    if (hash.length !== 64 || !/^[0-9a-f]+$/.test(hash)) {
      setLoading(false);
      const text = "El identificador del recibo debe ser un hash hexadecimal de 64 caracteres.";
      setError(text);
      notify.error(text);
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    setLoading(true);
    setError(null);
    setData(null);

    void fetch(`${apiUrl}/api/v1/public/receipts/${hash}`, { cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as PublicReceiptPayload;
        if (response.status === 404) {
          const text = "No se encontró un recibo con este identificador.";
          setError(text);
          notify.error(text);
          return;
        }
        if (!response.ok) {
          const text = formatApiError(payload, "No se pudo consultar el recibo.");
          setError(text);
          notify.error(text);
          return;
        }
        setData(payload);
      })
      .catch(() => {
        const text = "No se pudo contactar la API pública.";
        setError(text);
        notify.error(text);
      })
      .finally(() => setLoading(false));
  }, [params.receiptHash]);

  return (
    <main className="empty-state">
      <span className="eyebrow">Verificación pública</span>
      <h1>Recibo de boleta cifrada</h1>
      <p>
        Esta página confirma únicamente la existencia de una boleta registrada. No revela el
        contenido del voto ni la identidad del elector.
      </p>

      {loading ? <p className="form-message">Consultando recibo…</p> : null}
      {error ? (
        <p className="form-message" role="alert">
          {error}
        </p>
      ) : null}

      {data ? (
        <section className="mt-6 w-full max-w-lg text-left" aria-label="Resultado de verificación">
          <p className="form-message text-emerald-800 dark:text-emerald-200">
            Este recibo corresponde a una boleta cifrada registrada.
          </p>
          <dl className="mt-4 space-y-3 text-sm text-[var(--ink)]">
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">Estado</dt>
              <dd className="font-semibold">{data.status}</dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">Elección</dt>
              <dd className="font-semibold">{data.election_title}</dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">Estado de la elección</dt>
              <dd className="font-semibold">{data.election_status}</dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">ID de elección</dt>
              <dd className="break-all font-mono text-xs">{data.election_id}</dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">ID de papeleta</dt>
              <dd className="break-all font-mono text-xs">{data.ballot_id}</dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-[var(--muted)]">Registrado ({APP_TIMEZONE})</dt>
              <dd className="font-semibold">{formatAppDateTime(data.recorded_at)}</dd>
            </div>
            <div className="flex flex-col gap-1">
              <dt className="text-[var(--muted)]">Hash del recibo</dt>
              <dd className="mt-1 break-all font-mono text-xs leading-relaxed">
                {data.receipt_hash}
              </dd>
            </div>
          </dl>
          <p className="mt-6 text-xs text-[var(--muted)]">
            La verificación pública no incluye plancha, payload cifrado, prueba ZKP ni datos del
            elector.
          </p>
        </section>
      ) : null}
    </main>
  );
}
