export default function AdminPage() {
  return (
    <div className="page-shell narrow-shell">
      <span className="eyebrow">Realm ADMIN · COMISIÓN</span>
      <h1>Comisión electoral</h1>
      <p className="lead">Administración de elecciones, padrón, cierre, escrutinio y auditoría.</p>
      <div className="notice">
        <strong>Acceso protegido</strong>
        <p>Las acciones administrativas requerirán RBAC, organización activa, MFA y auditoría.</p>
      </div>
    </div>
  );
}
