type SurfaceCardProps = {
  title: string;
  description: string;
  href: string;
  audience: string;
};

export function SurfaceCard({ title, description, href, audience }: SurfaceCardProps) {
  return (
    <a
      className="block rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-6 transition hover:-translate-y-0.5 hover:border-[var(--primary)]"
      href={href}
    >
      <span className="text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--primary)]">
        {audience}
      </span>
      <h3 className="mt-2 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-[var(--muted)]">{description}</p>
      <span className="mt-5 block text-sm font-extrabold text-[var(--primary)]">Ingresar →</span>
    </a>
  );
}
