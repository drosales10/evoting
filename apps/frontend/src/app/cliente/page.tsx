import Link from "next/link";

import { CeremonyLiveBanner } from "@/components/ceremony/CeremonyLiveBanner";

export default function ClienteHomePage() {
  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-8 md:p-12">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--primary)]">
          Área cliente
        </p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight md:text-5xl">
          Resultados, territorio y ceremonia de escrutinio
        </h1>
        <p className="mt-4 max-w-2xl text-[var(--muted)]">
          Consulta elecciones, sigue el live de YouTube del cierre y la publicación de resultados,
          y explora la participación en el geovisor.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link className="btn btn-primary" href="/cliente/ceremonia">
            Ver ceremonia
          </Link>
          <Link className="btn btn-secondary" href="/cliente/geovisor">
            Abrir geovisor
          </Link>
          <Link className="btn btn-secondary" href="/cliente/elecciones">
            Ver elecciones
          </Link>
          <Link className="btn btn-secondary" href="/vote/login">
            Emitir voto
          </Link>
        </div>
      </section>

      <CeremonyLiveBanner />
    </div>
  );
}
