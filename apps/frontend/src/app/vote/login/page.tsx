import Link from "next/link";

import { RealmLoginForm } from "@/components/auth/realm-login-form";

export default function VoterLoginPage() {
  return (
    <div className="page-shell narrow-shell">
      <div className="auth-card voter-auth-card">
        <span className="eyebrow">Realm VOTER</span>
        <h1>Acceso del elector</h1>
        <p className="lead">
          Solicita un código de un solo uso para consultar tu elección. La respuesta no revela si
          un identificador pertenece al padrón.
        </p>
        <RealmLoginForm
          realm="VOTER"
          identifierLabel="Correo o documento"
          submitLabel="Solicitar o verificar OTP"
          mfaCopy="El OTP se envía al correo del elector cuando Mailtrap está configurado; en el piloto local también puede consultarse en la terminal del backend."
        />
        <Link className="back-link" href="/">
          ← Volver al inicio
        </Link>
      </div>
    </div>
  );
}
