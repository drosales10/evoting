"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { DashboardShell } from "@/components/admin/DashboardShell";
import { StatuteDocument } from "@/components/statute/StatuteDocument";
import { adminFetch } from "@/lib/admin-api";
import { formatApiError } from "@/lib/api-error";
import { datetimeLocalToUtcIso, formatAppDateTime } from "@/lib/datetime";
import { notify } from "@/lib/notify";
import type { StatuteArticleResult, StatuteTitleNode } from "@/lib/statute";

type Summary = {
  id: string;
  title: string;
  status: string;
  start_time: string;
  end_time: string;
  quorum_threshold_pct: string;
  approval_threshold_pct: string;
  article_count: number;
};

type Detail = Summary & {
  article_set_hash: string | null;
  titles: StatuteTitleNode[];
};

type ResultsPayload = {
  title: string;
  artifact: {
    quorum_met?: boolean;
    ballot_count?: number;
    articles?: StatuteArticleResult[];
  };
};

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    return formatApiError(await response.json(), fallback);
  } catch {
    return fallback;
  }
}

export function StatuteManager() {
  const [items, setItems] = useState<Summary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [results, setResults] = useState<ResultsPayload | null>(null);
  const [title, setTitle] = useState("Reforma de estatutos");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [quorum, setQuorum] = useState("30");
  const [approval, setApproval] = useState("50");
  const [publicKey, setPublicKey] = useState("");
  const [signingKey, setSigningKey] = useState("");
  const [closeReason, setCloseReason] = useState("Cierre de la consulta de estatutos");
  const [tallyText, setTallyText] = useState("");
  const [tallyReason, setTallyReason] = useState("Publicación del acta de estatutos");
  const [forcePilot, setForcePilot] = useState(false);

  const loadList = useCallback(async () => {
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes`);
    if (!response.ok) {
      notify.apiError(await response.json().catch(() => null), "No se pudieron listar las consultas");
      return;
    }
    setItems((await response.json()) as Summary[]);
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes/${id}`);
    if (!response.ok) {
      notify.apiError(await response.json().catch(() => null), "No se pudo abrir la consulta");
      return;
    }
    const payload = (await response.json()) as Detail;
    setDetail(payload);
    setSelectedId(id);
    if (payload.status === "TALLIED") {
      const resultsResponse = await adminFetch(`${apiUrl()}/api/v1/admin/statutes/${id}/results`);
      if (resultsResponse.ok) setResults((await resultsResponse.json()) as ResultsPayload);
    } else {
      setResults(null);
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  async function createConsultation(event: FormEvent) {
    event.preventDefault();
    let startTime: string;
    let endTime: string;
    try {
      startTime = datetimeLocalToUtcIso(start);
      endTime = datetimeLocalToUtcIso(end);
    } catch (error: unknown) {
      notify.error(error instanceof Error ? error.message : "Fecha inválida");
      return;
    }
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        start_time: startTime,
        end_time: endTime,
        quorum_threshold_pct: quorum,
        approval_threshold_pct: approval,
      }),
    });
    if (!response.ok) {
      notify.error(await readError(response, "No se pudo crear la consulta"));
      return;
    }
    const created = (await response.json()) as Detail;
    notify.success("Consulta creada");
    await loadList();
    setDetail(created);
    setSelectedId(created.id);
  }

  async function mutate(path: string, body?: unknown, method = "POST") {
    if (!selectedId) return;
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes/${selectedId}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      notify.error(await readError(response, "No se pudo completar la acción"));
      return;
    }
    if (response.status !== 204) {
      const payload = (await response.json()) as Detail | { status?: string };
      if (payload && "titles" in payload) setDetail(payload);
    }
    if (method === "DELETE") {
      setDetail(null);
      setSelectedId(null);
      setResults(null);
      notify.success("Borrador eliminado");
      await loadList();
      return;
    }
    notify.success("Consulta actualizada");
    await loadList();
    if (selectedId) await loadDetail(selectedId);
  }

  async function publishTally() {
    if (!selectedId) return;
    let parsed: { artifact?: unknown; signature?: string };
    try {
      parsed = JSON.parse(tallyText) as { artifact?: unknown; signature?: string };
    } catch {
      notify.error("El acta debe ser el JSON que devuelve el escrutinio local");
      return;
    }
    if (!parsed.artifact || !parsed.signature) {
      notify.error("El JSON necesita artifact y signature");
      return;
    }
    await mutate("/tally", {
      artifact: parsed.artifact,
      signature: parsed.signature,
      reason: tallyReason,
      pilot_override: forcePilot,
      approval_stage: "publish",
    });
  }

  const editable = detail?.status === "DRAFT" || detail?.status === "REGISTRATION";

  return (
    <DashboardShell>
      <div className="space-y-6 text-[var(--ink)]">
        <section className="card-panel">
          <h2 className="text-xl font-semibold">Nueva consulta de estatutos</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            El miembro envía una boleta cifrada. Al escrutar, cada respuesta queda con su nombre.
          </p>
          <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={(event) => void createConsultation(event)}>
            <label className="text-sm font-bold md:col-span-2">
              Título
              <input className="input-field mt-1" value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>
            <label className="text-sm font-bold">
              Apertura
              <input className="input-field mt-1" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} required />
            </label>
            <label className="text-sm font-bold">
              Cierre
              <input className="input-field mt-1" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} required />
            </label>
            <label className="text-sm font-bold">
              Quórum de participación %
              <input className="input-field mt-1" value={quorum} onChange={(event) => setQuorum(event.target.value)} required />
            </label>
            <label className="text-sm font-bold">
              Umbral para aprobar un artículo %
              <input className="input-field mt-1" value={approval} onChange={(event) => setApproval(event.target.value)} required />
            </label>
            <div className="md:col-span-2">
              <button className="btn btn-primary" type="submit">
                Crear borrador
              </button>
            </div>
          </form>
        </section>

        <section className="card-panel">
          <h2 className="text-xl font-semibold">Consultas</h2>
          <ul className="mt-3 space-y-2">
            {items.length === 0 ? <li className="text-sm text-[var(--muted)]">Todavía no hay consultas.</li> : null}
            {items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-xl border border-[var(--line)] bg-[var(--background)] px-3 py-2 text-left"
                  onClick={() => void loadDetail(item.id)}
                >
                  <span>
                    <span className="font-semibold">{item.title}</span>
                    <span className="mt-0.5 block text-xs text-[var(--muted)]">
                      {item.status} · {item.article_count} artículos · cierra {formatAppDateTime(item.end_time)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {detail ? (
          <section className="card-panel space-y-4">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
                {detail.status}
              </p>
              <h2 className="text-2xl font-semibold">{detail.title}</h2>
              {detail.article_set_hash ? (
                <p className="mt-1 break-all text-xs text-[var(--muted)]">Huella {detail.article_set_hash}</p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2">
              {detail.status === "DRAFT" ? (
                <button type="button" className="btn btn-primary" onClick={() => void mutate("/open-registration")}>
                  Abrir registro
                </button>
              ) : null}
              {detail.status === "REGISTRATION" ? (
                <button type="button" className="btn btn-primary" onClick={() => void mutate("/freeze")}>
                  Congelar texto y padrón
                </button>
              ) : null}
              {detail.status === "DRAFT" ? (
                <button
                  type="button"
                  className="btn btn-secondary text-[var(--ink)]"
                  onClick={() => void mutate("", undefined, "DELETE")}
                >
                  Eliminar borrador
                </button>
              ) : null}
            </div>

            {editable ? <StructureEditor detail={detail} onSaved={() => void loadDetail(detail.id)} /> : null}

            {detail.status === "FREEZE" ? (
              <div className="space-y-2">
                <p className="text-sm text-[var(--muted)]">
                  Pega las claves públicas que genera <code>scripts/generate_election_keys.py</code>. La privada no se guarda.
                </p>
                <textarea className="input-field min-h-28 font-mono text-xs" placeholder="Clave pública de cifrado" value={publicKey} onChange={(event) => setPublicKey(event.target.value)} />
                <textarea className="input-field min-h-28 font-mono text-xs" placeholder="Clave pública de firma (opcional)" value={signingKey} onChange={(event) => setSigningKey(event.target.value)} />
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() =>
                    void mutate("/activate", {
                      public_key: publicKey,
                      signing_public_key: signingKey.trim() || null,
                    })
                  }
                >
                  Activar consulta
                </button>
              </div>
            ) : null}

            {detail.status === "ACTIVE" ? (
              <div className="space-y-2">
                <label className="block text-sm font-bold">
                  Motivo de cierre
                  <input className="input-field mt-1" value={closeReason} onChange={(event) => setCloseReason(event.target.value)} />
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={forcePilot} onChange={(event) => setForcePilot(event.target.checked)} />
                  Cierre de piloto, si el entorno de prueba lo permite
                </label>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void mutate("/close", { reason: closeReason, force_pilot: forcePilot })}
                >
                  Cerrar consulta
                </button>
              </div>
            ) : null}

            {detail.status === "CLOSED" ? (
              <div className="space-y-2">
                <p className="text-sm text-[var(--muted)]">
                  Ejecuta <code>python -m scripts.tally_statute_ballots</code> y pega aquí su JSON.
                </p>
                <textarea className="input-field min-h-40 font-mono text-xs" value={tallyText} onChange={(event) => setTallyText(event.target.value)} />
                <input className="input-field" value={tallyReason} onChange={(event) => setTallyReason(event.target.value)} />
                <button type="button" className="btn btn-primary" onClick={() => void publishTally()}>
                  Publicar acta
                </button>
              </div>
            ) : null}

            <StatuteDocument titles={detail.titles} results={results?.artifact.articles} />
          </section>
        ) : null}
      </div>
    </DashboardShell>
  );
}

function StructureEditor({ detail, onSaved }: { detail: Detail; onSaved: () => void }) {
  const [titleNumber, setTitleNumber] = useState(String((detail.titles.at(-1)?.number ?? 0) + 1));
  const [titleDescription, setTitleDescription] = useState("");
  const [chapterTitleId, setChapterTitleId] = useState(detail.titles[0]?.id ?? "");
  const [chapterNumber, setChapterNumber] = useState("1");
  const [chapterDescription, setChapterDescription] = useState("");
  const [articleChapterId, setArticleChapterId] = useState(detail.titles[0]?.chapters[0]?.id ?? "");
  const [articleNumber, setArticleNumber] = useState("1");
  const [articleContent, setArticleContent] = useState("");

  async function post(path: string, body: unknown) {
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes/${detail.id}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      notify.error(await readError(response, "No se pudo guardar"));
      return;
    }
    notify.success("Texto guardado");
    onSaved();
  }

  async function remove(path: string) {
    const response = await adminFetch(`${apiUrl()}/api/v1/admin/statutes/${detail.id}${path}`, {
      method: "DELETE",
    });
    if (!response.ok && response.status !== 204) {
      notify.error(await readError(response, "No se pudo eliminar"));
      return;
    }
    onSaved();
  }

  return (
    <div className="space-y-4 rounded-xl border border-[var(--line)] bg-[var(--background)] p-4">
      <h3 className="font-semibold">Armar el estatuto</h3>
      <form
        className="grid gap-2 md:grid-cols-[8rem_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          void post("/titles", { number: Number(titleNumber), description: titleDescription, display_order: Number(titleNumber) });
        }}
      >
        <input className="input-field" type="number" min={1} value={titleNumber} onChange={(event) => setTitleNumber(event.target.value)} required />
        <input className="input-field" placeholder="Descripción del título" value={titleDescription} onChange={(event) => setTitleDescription(event.target.value)} required />
        <button className="btn btn-secondary text-[var(--ink)]" type="submit">Añadir título</button>
      </form>
      <form
        className="grid gap-2 md:grid-cols-[1fr_8rem_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          void post(`/titles/${chapterTitleId}/chapters`, {
            number: Number(chapterNumber),
            description: chapterDescription,
            display_order: Number(chapterNumber),
          });
        }}
      >
        <select className="input-field" value={chapterTitleId} onChange={(event) => setChapterTitleId(event.target.value)} required>
          <option value="">Título</option>
          {detail.titles.map((item) => (
            <option key={item.id} value={item.id}>
              Título {item.number}
            </option>
          ))}
        </select>
        <input className="input-field" type="number" min={1} value={chapterNumber} onChange={(event) => setChapterNumber(event.target.value)} required />
        <input className="input-field" placeholder="Descripción del capítulo" value={chapterDescription} onChange={(event) => setChapterDescription(event.target.value)} />
        <button className="btn btn-secondary text-[var(--ink)]" type="submit">Añadir capítulo</button>
      </form>
      <form
        className="grid gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void post(`/chapters/${articleChapterId}/articles`, {
            number: Number(articleNumber),
            content: articleContent,
            display_order: Number(articleNumber),
          });
        }}
      >
        <div className="grid gap-2 md:grid-cols-[1fr_8rem]">
          <select className="input-field" value={articleChapterId} onChange={(event) => setArticleChapterId(event.target.value)} required>
            <option value="">Capítulo</option>
            {detail.titles.flatMap((item) =>
              item.chapters.map((chapter) => (
                <option key={chapter.id} value={chapter.id}>
                  T{item.number} · Cap {chapter.number}
                </option>
              )),
            )}
          </select>
          <input className="input-field" type="number" min={1} value={articleNumber} onChange={(event) => setArticleNumber(event.target.value)} required />
        </div>
        <textarea className="input-field min-h-28" placeholder="Texto del artículo" value={articleContent} onChange={(event) => setArticleContent(event.target.value)} required />
        <button className="btn btn-primary w-fit" type="submit">Añadir artículo</button>
      </form>
      <ul className="space-y-1 text-sm">
        {detail.titles.map((item) => (
          <li key={item.id}>
            <span className="font-semibold">Título {item.number}. {item.description}</span>
            <button type="button" className="ml-2 text-[var(--muted)] underline" onClick={() => void remove(`/titles/${item.id}`)}>
              Quitar
            </button>
            <ul className="ml-4">
              {item.chapters.map((chapter) => (
                <li key={chapter.id}>
                  Capítulo {chapter.number}
                  {chapter.description ? `. ${chapter.description}` : ""}
                  <button type="button" className="ml-2 text-[var(--muted)] underline" onClick={() => void remove(`/chapters/${chapter.id}`)}>
                    Quitar
                  </button>
                  <ul className="ml-4">
                    {chapter.articles.map((article) => (
                      <li key={article.id}>
                        Artículo {article.number}
                        <button type="button" className="ml-2 text-[var(--muted)] underline" onClick={() => void remove(`/articles/${article.id}`)}>
                          Quitar
                        </button>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
