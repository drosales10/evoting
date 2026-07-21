"use client";

import { FormEvent, useState } from "react";

type RealmLoginFormProps = {
  realm: "ADMIN" | "VOTER";
  identifierLabel: string;
  submitLabel: string;
  mfaCopy: string;
};

export function RealmLoginForm({
  realm,
  identifierLabel,
  submitLabel,
  mfaCopy,
}: RealmLoginFormProps) {
  const [message, setMessage] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(
      realm === "ADMIN"
        ? "El acceso administrativo se habilitará después de activar la migración de autenticación y MFA."
        : "El flujo del elector solicitará un OTP sin revelar si el identificador pertenece al padrón.",
    );
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
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
      <button className="button button-primary" type="submit">
        {submitLabel}
      </button>
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </form>
  );
}
