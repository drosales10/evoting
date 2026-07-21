"use client";

import { useState, type FormEvent } from "react";

type RealmLoginFormProps = {
  realm: "ADMIN" | "VOTER";
  identifierLabel: string;
  submitLabel: string;
  mfaCopy: string;
};

type AdminCredentials = {
  organization_slug: string;
  email: string;
  password: string;
};

export function RealmLoginForm({
  realm,
  identifierLabel,
  submitLabel,
  mfaCopy,
}: RealmLoginFormProps) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mfaCredentials, setMfaCredentials] = useState<AdminCredentials | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setBusy(true);

    try {
      const form = new FormData(event.currentTarget);
      if (realm === "VOTER") {
        setMessage("La solicitud OTP será anti-enumerable; el proveedor de entrega aún no está configurado.");
        return;
      }

      const credentials: AdminCredentials = {
        organization_slug: String(form.get("organization_slug") ?? ""),
        email: String(form.get("identifier") ?? ""),
        password: String(form.get("credential") ?? ""),
      };
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/auth/admin/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
      });
      const payload = (await response.json()) as { status?: string; detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No fue posible iniciar sesión.");
      } else if (payload.status === "MFA_REQUIRED") {
        setMfaCredentials(credentials);
        setMessage("Credenciales correctas. Introduce el código de tu autenticador.");
      } else {
        setMessage("Sesión administrativa iniciada.");
      }
    } catch {
      setMessage("No se pudo contactar la API de autenticación.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMfaSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mfaCredentials) return;
    setMessage(null);
    setBusy(true);

    try {
      const form = new FormData(event.currentTarget);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/auth/admin/mfa/verify`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...mfaCredentials, code: String(form.get("code") ?? "") }),
      });
      const payload = (await response.json()) as { status?: string; detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "El código MFA no es válido.");
      } else if (payload.status === "AUTHENTICATED") {
        setMessage("Sesión administrativa iniciada.");
      }
    } catch {
      setMessage("No se pudo contactar la API de autenticación.");
    } finally {
      setBusy(false);
    }
  }

  if (realm === "ADMIN" && mfaCredentials) {
    return (
      <div className="auth-form">
        <p className="form-help">{mfaCopy}</p>
        <form onSubmit={handleMfaSubmit}>
          <label htmlFor="admin-mfa-code">Código de autenticación</label>
          <input
            id="admin-mfa-code"
            name="code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            minLength={6}
            maxLength={6}
            placeholder="Código de 6 dígitos"
            required
          />
          <button className="button button-primary" type="submit" disabled={busy}>
            {busy ? "Verificando…" : "Verificar MFA"}
          </button>
        </form>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      {realm === "ADMIN" ? (
        <>
          <label htmlFor="admin-organization">Organización</label>
          <input
            id="admin-organization"
            name="organization_slug"
            placeholder="organizacion-demo"
            required
          />
        </>
      ) : null}
      <label htmlFor={`${realm.toLowerCase()}-identifier`}>{identifierLabel}</label>
      <input
        id={`${realm.toLowerCase()}-identifier`}
        name="identifier"
        autoComplete={realm === "ADMIN" ? "username" : "email"}
        placeholder={realm === "ADMIN" ? "correo@organizacion.test" : "correo o documento"}
        required
      />
      <label htmlFor={`${realm.toLowerCase()}-password`}>
        {realm === "ADMIN" ? "Contraseña" : "Código OTP"}
      </label>
      <input
        id={`${realm.toLowerCase()}-password`}
        name="credential"
        type={realm === "ADMIN" ? "password" : "text"}
        inputMode={realm === "VOTER" ? "numeric" : undefined}
        minLength={realm === "ADMIN" ? 12 : 6}
        maxLength={realm === "VOTER" ? 6 : 256}
        placeholder={realm === "ADMIN" ? "Mínimo 12 caracteres" : "Código de 6 dígitos"}
        required
      />
      <p className="form-help">{mfaCopy}</p>
      <button className="button button-primary" type="submit" disabled={busy}>
        {busy ? "Procesando…" : submitLabel}
      </button>
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </form>
  );
}
