import Link from "next/link";

import { RealmLoginForm } from "@/components/auth/realm-login-form";

export default function AdminLoginPage() {
  return (
    <div className="page-shell narrow-shell">
      <div className="auth-card">
        <span className="eyebrow">Realm ADMIN</span>
        <h1>Acceso de comisión</h1>
        <p className="lead">
          Entrada para comisión electoral, apoderados y candidatos. Este acceso nunca comparte
          cookies con el elector.
        </p>
        <RealmLoginForm
          realm="ADMIN"
          identifierLabel="Correo operativo"
          submitLabel="Iniciar sesión"
          mfaCopy="La sesión administrativa usa organización activa, RBAC y cookies separadas del elector."
        />
        <Link className="back-link" href="/admin">
          ← Volver a comisión
        </Link>
      </div>
    </div>
  );
}
