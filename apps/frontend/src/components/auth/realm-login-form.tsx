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
  const [voterChallengeId, setVoterChallengeId] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setBusy(true);

    try {
      const form = new FormData(event.currentTarget);
      if (realm === "VOTER") {
        const organizationSlug = String(form.get("organization_slug") ?? "").trim();
        const identifier = String(form.get("identifier") ?? "").trim();
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const response = await fetch(`${apiUrl}/api/v1/auth/voter/request-otp`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ organization_slug: organizationSlug, identifier }),
        });
        const payload = (await response.json()) as {
          message?: string;
          detail?: string;
          challenge_id?: string | null;
        };
        if (!response.ok) {
          setMessage(payload.detail ?? "No fue posible solicitar el OTP.");
        } else if (payload.challenge_id) {
          setVoterChallengeId(payload.challenge_id);
          setMessage("Solicitud aceptada. Introduce el código OTP de desarrollo.");
        } else {
          setMessage(payload.message ?? "Si el elector es elegible, recibirá un OTP.");
        }
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
      const payload = (await response.json()) as {
        status?: string;
        detail?: string;
        csrf_token?: string;
      };
      if (!response.ok) {
        setMessage(payload.detail ?? "No fue posible iniciar sesión.");
      } else if (payload.status === "MFA_REQUIRED") {
        setMfaCredentials(credentials);
        setMessage("Credenciales correctas. Introduce el código de tu autenticador.");
      } else {
        if (payload.csrf_token) {
          window.sessionStorage.setItem("evoting_admin_csrf", payload.csrf_token);
        }
        setMessage("Sesión administrativa iniciada.");
        window.location.assign("/admin");
      }
    } catch {
      setMessage("No se pudo contactar la API de autenticación.");
    } finally {
      setBusy(false);
    }
  }

  async function handleVoterVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!voterChallengeId) return;
    setMessage(null);
    setBusy(true);
    try {
      const form = new FormData(event.currentTarget);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/auth/voter/verify-otp`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_id: voterChallengeId,
          code: String(form.get("code") ?? ""),
        }),
      });
      const payload = (await response.json()) as { csrf_token?: string; detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "El código OTP no es válido.");
        return;
      }
      if (!payload.csrf_token) {
        setMessage("La sesión VOTER no devolvió protección CSRF.");
        return;
      }
      window.sessionStorage.setItem("evoting_voter_csrf", payload.csrf_token);
      window.location.assign("/vote");
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
      const payload = (await response.json()) as {
        status?: string;
        detail?: string;
        csrf_token?: string;
      };
      if (!response.ok) {
        setMessage(payload.detail ?? "El código MFA no es válido.");
      } else if (payload.status === "AUTHENTICATED") {
        if (payload.csrf_token) {
          window.sessionStorage.setItem("evoting_admin_csrf", payload.csrf_token);
        }
        setMessage("Sesión administrativa iniciada.");
        window.location.assign("/admin");
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

  if (realm === "VOTER" && voterChallengeId) {
    return (
      <div className="auth-form">
        <p className="form-help">Introduce el código recibido por correo. En el piloto local, también se registra en la terminal del backend.</p>
        <form onSubmit={handleVoterVerify}>
          <label htmlFor="voter-otp-code">Código OTP</label>
          <input
            id="voter-otp-code"
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
            {busy ? "Verificando…" : "Verificar OTP"}
          </button>
        </form>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </div>
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      {realm === "ADMIN" || realm === "VOTER" ? (
        <>
          <label htmlFor={`${realm.toLowerCase()}-organization`}>Organización</label>
          <input
            id={`${realm.toLowerCase()}-organization`}
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
      {realm === "ADMIN" ? (
        <>
          <label htmlFor="admin-password">Contraseña</label>
          <input
            id="admin-password"
            name="credential"
            type="password"
            minLength={12}
            maxLength={256}
            placeholder="Mínimo 12 caracteres"
            required
          />
        </>
      ) : null}
      <p className="form-help">{mfaCopy}</p>
      <button className="button button-primary" type="submit" disabled={busy}>
        {busy ? "Procesando…" : submitLabel}
      </button>
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </form>
  );
}
