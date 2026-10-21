"use client";

import type { StatuteArticleResult, StatuteTitleNode } from "@/lib/statute";

type StatuteDocumentProps = {
  titles: StatuteTitleNode[];
  results?: StatuteArticleResult[];
};

export function StatuteDocument({ titles, results }: StatuteDocumentProps) {
  const byArticle = new Map((results ?? []).map((item) => [item.article_id, item]));

  return (
    <div className="statute-document space-y-8 text-[var(--ink)]" id="statute-document">
      {titles.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">Este estatuto todavía no tiene títulos.</p>
      ) : null}
      {titles.map((title) => (
        <section key={title.id} className="space-y-4">
          <h2 className="text-xl font-semibold">
            Título {title.number}. {title.description}
          </h2>
          {title.chapters.map((chapter) => (
            <div key={chapter.id} className="space-y-3">
              <h3 className="text-base font-bold text-[var(--primary-dark)] dark:text-[var(--primary)]">
                Capítulo {chapter.number}
                {chapter.description ? `. ${chapter.description}` : ""}
              </h3>
              {chapter.articles.map((article) => {
                const result = byArticle.get(article.id);
                return (
                  <article
                    key={article.id}
                    className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4"
                  >
                    <p className="text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--muted)]">
                      Artículo {article.number}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{article.content}</p>
                    {result ? (
                      <div className="mt-4 border-t border-[var(--line)] pt-3">
                        <p className="text-sm font-bold">
                          {result.meets_threshold ? "Aprobado" : "No aprobado"} ·{" "}
                          {result.approved_count} a favor · {result.rejected_count} en contra
                        </p>
                        <ul className="mt-3 space-y-2">
                          {result.responses.map((response) => (
                            <li
                              key={response.member_id}
                              className="rounded-lg border border-[var(--line)] bg-[var(--background)] px-3 py-2 text-sm"
                            >
                              <p className="font-semibold">
                                {response.full_name}
                                {response.registry_code ? ` · ${response.registry_code}` : ""}
                                {" · "}
                                {response.approved ? "Aprueba" : "No aprueba"}
                              </p>
                              {response.comment ? (
                                <p className="mt-1 whitespace-pre-wrap text-[var(--muted)]">
                                  {response.comment}
                                </p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
