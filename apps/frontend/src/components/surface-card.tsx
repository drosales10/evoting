type SurfaceCardProps = {
  title: string;
  description: string;
  href: string;
  audience: string;
};

export function SurfaceCard({ title, description, href, audience }: SurfaceCardProps) {
  return (
    <a className="surface-card" href={href}>
      <span className="eyebrow">{audience}</span>
      <h3>{title}</h3>
      <p>{description}</p>
      <span className="card-link">Ingresar →</span>
    </a>
  );
}
