"use client";

export type CeremonyMilestone = {
  type: string;
  label: string;
  at: string;
  note?: string | null;
};

export type CeremonyBroadcast = {
  election_id: string;
  title: string;
  description: string | null;
  status: string;
  youtube_url: string;
  embed_url: string;
  scheduled_start_at: string | null;
  went_live_at: string | null;
  ended_at: string | null;
  artifact_sha256: string | null;
  verify_path?: string | null;
  milestones: CeremonyMilestone[];
  has_key_compare_milestone?: boolean;
};

export function statusLabel(status: string) {
  switch (status) {
    case "LIVE":
      return "En vivo";
    case "SCHEDULED":
      return "Programada";
    case "ENDED":
      return "Finalizada";
    case "ARCHIVED":
      return "Archivada";
    default:
      return status;
  }
}

export function CeremonyPlayer({ broadcast }: { broadcast: CeremonyBroadcast }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--primary)]">
            {statusLabel(broadcast.status)}
          </p>
          <h3 className="mt-1 text-lg font-semibold">{broadcast.title}</h3>
        </div>
        <a
          className="btn btn-secondary !px-3 !py-1.5 text-xs"
          href={broadcast.youtube_url}
          target="_blank"
          rel="noreferrer"
        >
          Abrir en YouTube
        </a>
      </div>
      {broadcast.description ? (
        <p className="text-sm text-[var(--muted)]">{broadcast.description}</p>
      ) : null}
      <div className="aspect-video overflow-hidden rounded-xl border border-[var(--line)] bg-black/40">
        <iframe
          title={broadcast.title}
          src={broadcast.embed_url}
          className="h-full w-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
      <ol className="space-y-2 border-t border-[var(--line)] pt-3">
        {broadcast.milestones.length === 0 ? (
          <li className="text-sm text-[var(--muted)]">Aún no hay hitos registrados.</li>
        ) : (
          broadcast.milestones.map((milestone) => (
            <li key={`${milestone.type}-${milestone.at}`} className="text-sm">
              <span className="font-semibold">{milestone.label}</span>
              <span className="text-[var(--muted)]">
                {" · "}
                {new Date(milestone.at).toLocaleString("es-ES")}
              </span>
              {milestone.note ? (
                <p className="text-[var(--muted)]">{milestone.note}</p>
              ) : null}
            </li>
          ))
        )}
      </ol>
      {broadcast.artifact_sha256 ? (
        <p className="break-all text-xs text-[var(--muted)]">
          Artefacto:{" "}
          <a className="underline" href={broadcast.verify_path ?? `/verify/${broadcast.artifact_sha256}`}>
            {broadcast.artifact_sha256}
          </a>
        </p>
      ) : null}
    </div>
  );
}
