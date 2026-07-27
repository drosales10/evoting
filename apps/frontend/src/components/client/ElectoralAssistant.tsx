"use client";

import { Info } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type AssistantStatus = {
  provider: string;
  gemini_configured: boolean;
  assistant_available: boolean;
  model_id: string | null;
};

type ChatTurn = {
  role: "user" | "assistant";
  text: string;
  disclaimer?: string;
};

const DEFAULT_ASSISTANT_DISCLAIMER =
  "Asistente informativo (Gemini). No forma parte de la urna, no ve boletas ni claves privadas.";

const SUGGESTIONS = [
  "¿Cómo se cifra mi voto?",
  "¿Qué es el recibo con código QR?",
  "¿Cómo verifico el resultado sin confiar solo en la web?",
  "¿Gemini puede ver mi boleta?",
];

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg?: string }).msg ?? JSON.stringify(item));
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (detail == null) return "No se pudo consultar Gemini";
  return JSON.stringify(detail);
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) {
    throw new Error(`Respuesta vacía (HTTP ${response.status})`);
  }
  try {
    return JSON.parse(trimmed) as T;
  } catch {
    const preview = trimmed.slice(0, 140).replace(/\s+/g, " ");
    throw new Error(
      `El servidor no devolvió JSON (HTTP ${response.status}). ` +
        `Revisa que la API esté en :8000. Inicio: ${preview}`,
    );
  }
}

function clientApiBase(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  if (typeof window !== "undefined") {
    // Same origin when env missing (production behind nginx).
    return "";
  }
  return "http://localhost:8000";
}

export function ElectoralAssistant() {
  // null until mounted — avoids SSR freezing a wrong host into useState.
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setApiBase(clientApiBase());
  }, []);

  const refreshStatus = useCallback(async () => {
    if (apiBase == null) {
      throw new Error("API base aún no lista");
    }
    const response = await fetch(`${apiBase}/api/v1/public/assistant/status`, {
      cache: "no-store",
    });
    return readJson<AssistantStatus>(response);
  }, [apiBase]);

  useEffect(() => {
    if (apiBase == null) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await refreshStatus();
        if (!cancelled) {
          setStatus(data);
          setStatusError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus(null);
          setStatusError(err instanceof Error ? err.message : "No se pudo leer status");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBase, refreshStatus]);

  async function ask(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (trimmed.length < 3 || pending || apiBase == null) return;
    setError(null);
    setQuestion("");
    setTurns((prev) => [...prev, { role: "user", text: trimmed }]);
    setPending(true);
    try {
      const live = await refreshStatus();
      setStatus(live);
      setStatusError(null);
      if (!live.assistant_available) {
        throw new Error(
          "Gemini no está disponible en este backend. Revisa GEMINI_ENABLED y GEMINI_API_KEY en el .env de la raíz, luego reinicia la API.",
        );
      }

      const response = await fetch(`${apiBase}/api/v1/public/assistant/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const payload = await readJson<{
        answer?: string;
        detail?: unknown;
        disclaimer?: string;
      }>(response);
      if (!response.ok) {
        throw new Error(formatApiDetail(payload.detail));
      }
      const answer = payload.answer ?? "Sin respuesta";
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          text: answer,
          disclaimer: payload.disclaimer?.trim() || DEFAULT_ASSISTANT_DISCLAIMER,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de red");
    } finally {
      setPending(false);
    }
  }

  const available = Boolean(status?.assistant_available);
  const statusLabel =
    apiBase == null
      ? "iniciando…"
      : statusError != null
        ? "error de status"
        : status == null
          ? "comprobando…"
          : available
            ? "disponible"
            : "no configurado";

  return (
    <section className="rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-6 md:p-8">
      <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--primary)]">
        Google Gemini
      </p>
      <h2 className="mt-2 text-2xl font-semibold tracking-tight md:text-3xl">
        Asistente electoral
      </h2>
      <p className="mt-3 max-w-2xl text-sm text-[var(--muted)]">
        Preguntas frecuentes sobre el proceso. El asistente vive fuera de la urna: no ve boletas,
        claves privadas ni el padrón nominativo.
      </p>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full border border-[var(--line)] px-3 py-1">
          Gemini: {statusLabel}
        </span>
        {status?.model_id ? (
          <span className="rounded-full border border-[var(--line)] px-3 py-1">
            Modelo: {status.model_id}
          </span>
        ) : null}
        <span className="rounded-full border border-[var(--line)] px-3 py-1">
          API: {apiBase ?? "…"}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {SUGGESTIONS.map((item) => (
          <button
            key={item}
            type="button"
            className="btn btn-secondary text-left text-sm"
            disabled={pending || apiBase == null || status?.assistant_available === false}
            onClick={() => void ask(item)}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-3">
        {turns.map((turn, index) => (
          <div
            key={`${turn.role}-${index}`}
            className={
              turn.role === "user"
                ? "rounded-2xl border border-[var(--line)] bg-[var(--background)] px-4 py-3 text-sm"
                : "rounded-2xl border border-[var(--primary)]/30 bg-[var(--primary)]/10 px-3 py-3 text-sm whitespace-pre-wrap"
            }
          >
            <div className="mb-1 flex items-center gap-1.5">
              <p className="text-[0.65rem] font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
                {turn.role === "user" ? "Tú" : "Gemini"}
              </p>
              {turn.role === "assistant" && turn.disclaimer ? (
                <span
                  className="inline-flex text-[var(--muted)]"
                  title={turn.disclaimer}
                >
                  <Info
                    className="h-3.5 w-3.5"
                    aria-hidden="true"
                    strokeWidth={2.25}
                  />
                  <span className="sr-only">{turn.disclaimer}</span>
                </span>
              ) : null}
            </div>
            {turn.text}
          </div>
        ))}
      </div>

      <form
        className="mt-5 flex flex-col gap-3 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(question);
        }}
      >
        <input
          className="field"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Escribe tu pregunta sobre el proceso electoral…"
          maxLength={2000}
          disabled={pending || apiBase == null}
        />
        <button
          className="btn btn-primary shrink-0"
          type="submit"
          disabled={pending || apiBase == null}
        >
          {pending ? "Consultando…" : "Preguntar"}
        </button>
      </form>

      {error ? (
        <p className="mt-3 text-sm text-rose-700 dark:text-rose-300" role="alert">
          {error}
        </p>
      ) : null}

      {statusError ? (
        <p className="mt-3 text-sm text-rose-700 dark:text-rose-300" role="alert">
          No se pudo consultar el status: {statusError}
        </p>
      ) : null}

      {status && !status.assistant_available ? (
        <p className="mt-3 text-sm text-[var(--muted)]">
          Para activarlo:{" "}
          <code className="text-[var(--ink)]">GEMINI_ENABLED=true</code> y{" "}
          <code className="text-[var(--ink)]">GEMINI_API_KEY</code> en el{" "}
          <code className="text-[var(--ink)]">.env</code> de la raíz, luego reinicia la API.
        </p>
      ) : null}
    </section>
  );
}
