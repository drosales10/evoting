import Link from "next/link";

import { AdminOverview } from "@/components/admin/admin-overview";

export default function AdminPage() {
  return (
    <div className="page-shell">
      <span className="eyebrow">Realm ADMIN · COMISIÓN</span>
      <h1>Comisión electoral</h1>
      <p className="lead">Administración de elecciones, padrón, cierre, escrutinio y auditoría.</p>
      <AdminOverview />
      <div className="hero-actions">
        <Link className="button button-primary" href="/admin/login">
          Acceder a comisión
        </Link>
      </div>
    </div>
  );
}
