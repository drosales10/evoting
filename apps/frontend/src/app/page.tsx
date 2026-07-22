import Link from "next/link";

import { SurfaceCard } from "@/components/surface-card";

const surfaces = [
  {
    title: "Portal público",
    description: "Consulta convocatorias y resultados publicados sin acceder al padrón.",
    href: "/elections",
    audience: "Público",
  },
  {
    title: "Área cliente",
    description: "Explora elecciones, resultados y el geovisor territorial en modo oscuro.",
    href: "/cliente",
    audience: "Ciudadanía",
  },
  {
    title: "Espacio del elector",
    description: "Solicita un OTP y emite tu boleta cifrada.",
    href: "/vote/login",
    audience: "Elector",
  },
  {
    title: "Comisión electoral",
    description: "Padrón, territorio N1–N5, ciclo electoral y geovisor administrativo.",
    href: "/admin",
    audience: "Comisión",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
      <section className="relative overflow-hidden rounded-3xl border border-[var(--line)] bg-gradient-to-br from-[var(--accent)] via-[var(--surface)] to-[var(--background)] p-8 md:p-14">
        <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--primary)]">
          eVoting
        </p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-[var(--ink)] md:text-6xl">
          Elecciones digitales con confianza verificable.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-[var(--muted)]">
          Superficies separadas para comisión, electores y consulta pública, con territorio por
          región, estado y mesa.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link className="btn btn-primary" href="/cliente">
            Entrar al área cliente
          </Link>
          <Link className="btn btn-secondary" href="/admin">
            Ir a comisión
          </Link>
        </div>
      </section>

      <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Superficies">
        {surfaces.map((surface) => (
          <SurfaceCard key={surface.href} {...surface} />
        ))}
      </section>
    </div>
  );
}
