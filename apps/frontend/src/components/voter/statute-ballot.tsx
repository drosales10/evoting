"use client";

import { useEffect, useMemo, useState } from "react";

import { VoterBallotReceipt, type BallotReceiptData } from "@/components/voter/voter-ballot-receipt";
import { formatApiError } from "@/lib/api-error";
import { getVoterCsrfToken, voterFetch } from "@/lib/voter-api";
import {
  buildStatuteIntegrityProof,
  canonicalStatutePlaintext,
  randomNonceHex,
  sealPlaintext,
} from "@/lib/sealed-ballot";
import { flattenStatute, type StatuteTitleNode } from "@/lib/statute";
import { clientApiBase as apiUrl } from "@/lib/api-origin";

type Summary = {
  consultation_id: string;
  title: string;
  end_time: string;
  has_voted: boolean;
};

type Detail = {
  consultation_id: string;
  title: string;
  public_key: string;
  key_version: string;
  has_voted: boolean;
  article_set_hash: string;
  approval_threshold_pct: string;
  titles: StatuteTitleNode[];
};

type Choice = {
  approved: boolean | null;
  comment: string;
};


export function StatuteBallot() {
  const [summaries, setSummaries] = useState<Summary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [index, setIndex] = useState(0);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<BallotReceiptData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const base = apiUrl();
    void voterFetch(`${base}/api/v1/voter/statutes`, { cache: "no-store" })
      .then(async (response) => {
        if (response.status === 401) {
          setSummaries([]);
          return;
        }
        if (!response.ok) {
          setSummaries([]);
          return;
        }
        setSummaries((await response.json()) as Summary[]);
      })
      .catch(() => setSummaries([]));
  }, []);

  useEffect(() => {
    if (!summaries || summaries.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => current ?? summaries[0].consultation_id);
  }, [summaries]);

  useEffect(() => {
    if (!selectedId) return;
    setDetail(null);
    setIndex(0);
    setLoadError(null);
    void voterFetch(`${apiUrl()}/api/v1/voter/statutes/${selectedId}`, {
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) {
          setLoadError("No se pudo abrir esta consulta.");
          return;
        }
        const payload = (await response.json()) as Detail;
        setDetail(payload);
      })
      .catch(() => setLoadError("No se pudo cargar el estatuto."));
  }, [selectedId]);

  const articles = useMemo(() => (detail ? flattenStatute(detail.titles) : []), [detail]);
  const article = articles[index];
  const choice = article ? choices[article.id] : undefined;
  const answered = articles.filter((item) => choices[item.id]?.approved !== undefined && choices[item.id]?.approved !== null).length;

  function setChoice(articleId: string, next: Choice) {
    setChoices((current) => ({ ...current, [articleId]: next }));
  }

  async function submit() {
    if (!detail) return;
    const missing = articles.filter((item) => choices[item.id]?.approved == null);
    if (missing.length > 0) {
      setMessage("Falta marcar todos los artículos.");
      return;
    }
    const rejectedWithoutComment = articles.find((item) => {
      const row = choices[item.id];
      return row?.approved === false && !row.comment.trim();
    });
    if (rejectedWithoutComment) {
      setMessage(`El artículo ${rejectedWithoutComment.number} necesita un comentario para el rechazo.`);
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const nonce = randomNonceHex();
      const plaintext = canonicalStatutePlaintext(
        articles.map((item) => ({
          article_id: item.id,
          approved: Boolean(choices[item.id]?.approved),
          comment: choices[item.id]?.comment ?? "",
        })),
        nonce,
      );
      const sealed = await sealPlaintext(detail.public_key, plaintext, detail.key_version);
      const issuanceResponse = await voterFetch(
        `${apiUrl()}/api/v1/voter/statutes/${detail.consultation_id}/issuance-token`,
        { method: "POST" },
      );
      const issuancePayload = (await issuanceResponse.json()) as {
        issuance_token?: string;
        detail?: unknown;
      };
      if (!issuanceResponse.ok || !issuancePayload.issuance_token) {
        setMessage(formatApiError(issuancePayload, "No se pudo emitir el token de un solo uso."));
        return;
      }
      const zkpProof = await buildStatuteIntegrityProof(
        sealed.encryptedPayload,
        plaintext,
        detail.article_set_hash,
      );
      const csrfToken = getVoterCsrfToken();
      if (!csrfToken) {
        setMessage("La sesión no tiene protección CSRF. Inicia sesión nuevamente.");
        return;
      }
      const response = await voterFetch(
        `${apiUrl()}/api/v1/voter/statutes/${detail.consultation_id}/ballots`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          body: JSON.stringify({
            encrypted_payload: sealed.encryptedPayload,
            receipt_hash: sealed.receiptHash,
            zkp_proof: zkpProof,
            key_version: detail.key_version,
            issuance_token: issuancePayload.issuance_token,
          }),
        },
      );
      const payload = (await response.json()) as BallotReceiptData & {
        receipt_hash?: string;
        ballot_id?: string;
        recorded_at?: string;
        qr_payload?: string;
        detail?: unknown;
      };
      if (!response.ok || !payload.receipt_hash || !payload.ballot_id || !payload.recorded_at) {
        setMessage(formatApiError(payload, "No se pudo registrar la boleta."));
        return;
      }
      setReceipt({
        electionTitle: detail.title,
        electionId: detail.consultation_id,
        ballotId: payload.ballot_id,
        receiptHash: payload.receipt_hash,
        recordedAt: payload.recorded_at,
        keyVersion: detail.key_version,
        qrPayload: payload.qr_payload,
        subjectLabel: "Consulta",
        referenceLabel: "Ref. consulta",
      });
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "No se pudo cifrar la boleta.");
    } finally {
      setBusy(false);
    }
  }

  if (summaries === null) {
    return (
      <section className="card-panel mb-6">
        <p className="text-sm text-[var(--muted)]">Buscando consultas de estatutos…</p>
      </section>
    );
  }
  if (summaries.length === 0) {
    return null;
  }
  if (receipt) {
    return (
      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold text-[var(--ink)]">Estatuto enviado</h2>
        <VoterBallotReceipt receipt={receipt} />
      </section>
    );
  }
  if (!detail || !article) {
    return (
      <section className="card-panel mb-6">
        <p className="text-sm text-[var(--muted)]">
          {loadError ?? (detail && articles.length === 0
            ? "Esta consulta no tiene artículos para votar."
            : "Cargando el texto del estatuto…")}
        </p>
      </section>
    );
  }
  if (detail.has_voted) {
    return (
      <section className="card-panel mb-6">
        <h2 className="text-xl font-semibold">Estatuto</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Ya enviaste tu boleta de «{detail.title}». El contenido permanece cifrado hasta el escrutinio.
        </p>
      </section>
    );
  }

  const rejecting = choice?.approved === false;

  return (
    <section className="card-panel mb-8 text-[var(--ink)]">
      <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
        Consulta de estatuto
      </p>
      <h2 className="mt-1 text-2xl font-semibold">{detail.title}</h2>
      {summaries.length > 1 ? (
        <label className="mt-3 block text-sm font-bold">
          Consulta abierta
          <select
            className="input-field mt-1"
            value={detail.consultation_id}
            onChange={(event) => {
              setSelectedId(event.target.value);
              setIndex(0);
              setChoices({});
              setMessage(null);
            }}
          >
            {summaries.map((item) => (
              <option key={item.consultation_id} value={item.consultation_id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <p className="mt-1 text-sm text-[var(--muted)]">
        Una sola boleta. Aprueba cada artículo o explica el rechazo. Umbral de aprobación{" "}
        {detail.approval_threshold_pct}%.
      </p>
      <p className="mt-3 text-sm font-semibold">
        Artículo {index + 1} de {articles.length} · respondidos {answered}
      </p>

      <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--background)] p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
          Título {article.titleNumber}. {article.titleDescription}
          {" · "}
          Capítulo {article.chapterNumber}
          {article.chapterDescription ? `. ${article.chapterDescription}` : ""}
        </p>
        <h3 className="mt-2 text-lg font-semibold">Artículo {article.number}</h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{article.content}</p>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          className={
            choice?.approved === true
              ? "btn btn-primary"
              : "btn btn-secondary text-[var(--ink)]"
          }
          onClick={() => setChoice(article.id, { approved: true, comment: "" })}
        >
          Apruebo
        </button>
        <button
          type="button"
          className={
            rejecting
              ? "btn bg-rose-700 text-white hover:bg-rose-800 dark:bg-rose-900/70 dark:text-rose-50"
              : "btn btn-secondary text-[var(--ink)]"
          }
          onClick={() =>
            setChoice(article.id, { approved: false, comment: choice?.comment ?? "" })
          }
        >
          No apruebo
        </button>
      </div>

      {rejecting ? (
        <label className="mt-4 block text-sm font-bold">
          Comentario
          <textarea
            className="input-field mt-1 min-h-28"
            maxLength={2000}
            value={choice?.comment ?? ""}
            onChange={(event) =>
              setChoice(article.id, { approved: false, comment: event.target.value })
            }
            placeholder="Explica por qué no apruebas este artículo"
          />
        </label>
      ) : null}

      {message ? <p className="mt-3 text-sm font-semibold text-rose-700 dark:text-rose-200">{message}</p> : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-secondary text-[var(--ink)]"
          disabled={index === 0}
          onClick={() => setIndex((current) => Math.max(0, current - 1))}
        >
          Anterior
        </button>
        {index < articles.length - 1 ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setIndex((current) => current + 1)}
          >
            Siguiente
          </button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void submit()}>
            {busy ? "Cifrando…" : "Enviar boleta"}
          </button>
        )}
      </div>
    </section>
  );
}
