import Link from "next/link";

import { ElectoralAssistant } from "@/components/client/ElectoralAssistant";

export default function ClienteAsistentePage() {
  return (
    <div className="space-y-6">
      <section className="rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-6 md:p-8">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--primary)]">
          Asistente con IA
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
          Asistente con Google Gemini 3.5 Flash
        </h1>
        <p className="mt-3 max-w-2xl text-[var(--muted)]">
          FAQ del proceso electoral fuera del path de urna: Gemini no ve boletas, claves privadas ni
          el padrón nominativo.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link className="btn btn-secondary" href="/cliente">
            Volver al inicio
          </Link>
        </div>
      </section>

      <ElectoralAssistant />
    </div>
  );
}
