"use client";

import { useEffect, useState } from "react";

type AssistantStatus = {
  provider: string;
  gemini_configured: boolean;
  assistant_available: boolean;
  model_id: string | null;
};

type ChatTurn = {
  role: "user" | "assistant";
  text: string;
};

const SUGGESTIONS = [
  "¿Cómo se cifra mi voto?",
  "¿Qué es el recibo con código QR?",
  "¿Cómo verifico el resultado sin confiar solo en la web?",
  "¿Gemini puede ver mi boleta?",
];

export function ElectoralAssistant() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch(`${apiUrl}/api/v1/public/assistant/status`, {
          cache: "no-store",
        });
        if (!response.ok) return;
        const data = (await response.json()) as AssistantStatus;
        if (!cancelled) setStatus(data);
      } catch {
        if (!cancelled) setStatus(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiUrl]);

  async function ask(nextQuestion: string) {
    const trimmed = nextQuestion.trim();
    if (trimmed.length < 3 || pending) return;
    setError(null);
    setQuestion("");
    setTurns((prev) => [...prev, { role: "user", text: trimmed }]);
    setPending(true);
    try {
      const response = await fetch(`${apiUrl}/api/v1/public/assistant/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      const payload = (await response.json()) as {
        answer?: string;
        detail?: string;
        disclaimer?: string;
      };
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "No se pudo consultar Gemini",
        );
      }
      const answer = payload.answer ?? "Sin respuesta";
      const disclaimer = payload.disclaimer ? `\n\n_${payload.disclaimer}_` : "";
      setTurns((prev) => [...prev, { role: "assistant", text: `${answer}${disclaimer}` }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de red");
    } finally {
      setPending(false);
    }
  }

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
          Gemini: {status?.assistant_available ? "disponible" : "no configurado"}
        </span>
        {status?.model_id ? (
          <span className="rounded-full border border-[var(--line)] px-3 py-1">
            Modelo: {status.model_id}
          </span>
        ) : null}
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {SUGGESTIONS.map((item) => (
          <button
            key={item}
            type="button"
            className="btn btn-secondary text-left text-sm"
            disabled={pending || status?.assistant_available === false}
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
                : "rounded-2xl border border-[var(--primary)]/30 bg-[var(--primary)]/10 px-4 py-3 text-sm whitespace-pre-wrap"
            }
          >
            <p className="mb-1 text-[0.65rem] font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
              {turn.role === "user" ? "Tú" : "Gemini"}
            </p>
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
          disabled={pending}
        />
        <button className="btn btn-primary shrink-0" type="submit" disabled={pending}>
          {pending ? "Consultando…" : "Preguntar"}
        </button>
      </form>

      {error ? (
        <p className="mt-3 text-sm text-rose-700 dark:text-rose-300" role="alert">
          {error}
        </p>
      ) : null}

      {status && !status.assistant_available ? (
        <p className="mt-3 text-sm text-[var(--muted)]">
          Para activarlo:{" "}
          <code className="text-[var(--ink)]">GEMINI_ENABLED=true</code> y{" "}
          <code className="text-[var(--ink)]">GEMINI_API_KEY</code> (Google AI Studio).
        </p>
      ) : null}
    </section>
  );
}
