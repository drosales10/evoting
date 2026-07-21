import { SurfaceCard } from "@/components/surface-card";

const surfaces = [
  {
    title: "Portal público",
    description: "Consulta convocatorias y elecciones publicadas sin acceder a datos del padrón.",
    href: "/elections",
    audience: "Público",
  },
  {
    title: "Espacio del elector",
    description: "El acceso a la boleta requerirá identidad de elector, MFA y autorización de emisión.",
    href: "/vote",
    audience: "Elector",
  },
  {
    title: "Portal de apoderados",
    description: "Gestiona una plancha propia con permisos y ownership aislados.",
    href: "/party",
    audience: "Apoderado",
  },
  {
    title: "Comisión electoral",
    description: "Administra elecciones, padrón, revisión, cierre y auditoría con RBAC.",
    href: "/admin",
    audience: "Comisión",
  },
];

export default function HomePage() {
  return (
    <div className="page-shell">
      <section className="hero">
        <span className="eyebrow">Plataforma eVoting</span>
        <h1>Elecciones digitales con confianza verificable.</h1>
        <p>
          Esta primera versión establece las superficies del sistema y se conecta de forma no
          destructiva a la base de datos electoral existente.
        </p>
        <div className="hero-actions">
          <a className="button button-primary" href="/elections">
            Ver elecciones
          </a>
          <a className="button button-secondary" href="/admin">
            Ir a comisión
          </a>
        </div>
      </section>
      <section className="surface-grid" aria-label="Superficies de la plataforma">
        {surfaces.map((surface) => (
          <SurfaceCard key={surface.href} {...surface} />
        ))}
      </section>
    </div>
  );
}
