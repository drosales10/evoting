"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type VoterCandidate = {
  id: string;
  position_id: string;
  position_code: string;
  position_title: string;
  member_full_name: string;
};

type VoterSlate = {
  id: string;
  name: string;
  slogan: string | null;
  candidates: VoterCandidate[];
};

type VoterElection = {
  election_id: string;
  title: string;
  status: string;
  start_time: string;
  end_time: string;
  public_key: string;
  key_version: string;
  has_voted: boolean;
  slate_set_hash: string;
  zkp_verification_enabled: boolean;
  slates: VoterSlate[];
};

type VoterBallotResponse = {
  accepted: boolean;
  receipt_hash: string;
  ballot_id: string;
  recorded_at: string;
};

function toBase64(value: ArrayBuffer | Uint8Array): string {
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function toHex(value: ArrayBuffer): string {
  return Array.from(new Uint8Array(value), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return toHex(digest);
}

async function buildIntegrityProof(
  encryptedPayload: string,
  slateId: string,
  nonce: string,
  slateSetHash: string,
): Promise<string> {
  const commitment = await sha256Hex(`${slateId}:${nonce}`);
  const payloadBinding = await sha256Hex(`${encryptedPayload}:${commitment}`);
  const proof = JSON.stringify({
    version: "ballot-integrity-v1",
    commitment,
    payload_binding: payloadBinding,
    slate_set_hash: slateSetHash,
  });
  return toBase64(new TextEncoder().encode(proof));
}

async function encryptSelection(
  election: VoterElection,
  slateId: string,
): Promise<{ encryptedPayload: string; receiptHash: string; nonce: string }> {
  const publicKeyData = election.public_key
    .replace("-----BEGIN PUBLIC KEY-----", "")
    .replace("-----END PUBLIC KEY-----", "")
    .replace(/\s/g, "");
  const publicKeyBytes = Uint8Array.from(atob(publicKeyData), (character) => character.charCodeAt(0));
  const publicKey = await crypto.subtle.importKey(
    "spki",
    publicKeyBytes.buffer,
    { name: "RSA-OAEP", hash: "SHA-256" },
    false,
    ["encrypt"],
  );
  const aesKey = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt"],
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const nonceBytes = crypto.getRandomValues(new Uint8Array(16));
  const nonce = toHex(nonceBytes.buffer);
  const plaintext = new TextEncoder().encode(JSON.stringify({ slate_id: slateId, nonce }));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, aesKey, plaintext);
  const rawAesKey = await crypto.subtle.exportKey("raw", aesKey);
  const wrappedKey = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, publicKey, rawAesKey);
  const encryptedPayload = JSON.stringify({
    algorithm: "RSA-OAEP-256/AES-256-GCM",
    wrapped_key: toBase64(wrappedKey),
    iv: toBase64(iv.buffer),
    ciphertext: toBase64(ciphertext),
    key_version: election.key_version,
  });
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(encryptedPayload),
  );
  return {
    encryptedPayload,
    receiptHash: toHex(digest),
    nonce,
  };
}

export function VoterBallot() {
  const [electionId, setElectionId] = useState("");
  const [election, setElection] = useState<VoterElection | null>(null);
  const [selectedSlate, setSelectedSlate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<VoterBallotResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [voterSessionReady, setVoterSessionReady] = useState(false);

  useEffect(() => {
    setVoterSessionReady(Boolean(window.sessionStorage.getItem("evoting_voter_csrf")));
    setSessionChecked(true);
  }, []);

  async function loadElection() {
    setBusy(true);
    setMessage(null);
    setReceipt(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/voter/elections/${electionId.trim()}`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json()) as VoterElection & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo cargar la elección.");
        return;
      }
      setElection(payload);
      setSelectedSlate(payload.slates[0]?.id ?? "");
    } catch {
      setMessage("No se pudo contactar la API VOTER.");
    } finally {
      setBusy(false);
    }
  }

  async function castBallot() {
    if (!election || !selectedSlate) return;
    setBusy(true);
    setMessage(null);
    try {
      const encrypted = await encryptSelection(election, selectedSlate);
      const csrfToken = window.sessionStorage.getItem("evoting_voter_csrf");
      if (!csrfToken) {
        setMessage("La sesión VOTER no tiene protección CSRF. Inicia sesión nuevamente.");
        return;
      }
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const issuanceResponse = await fetch(
        `${apiUrl}/api/v1/voter/elections/${election.election_id}/issuance-token`,
        {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRF-Token": csrfToken },
        },
      );
      const issuancePayload = (await issuanceResponse.json()) as {
        issuance_token?: string;
        detail?: string;
      };
      if (!issuanceResponse.ok || !issuancePayload.issuance_token) {
        setMessage(issuancePayload.detail ?? "No se pudo emitir el token de un solo uso.");
        return;
      }
      const zkpProof = election.zkp_verification_enabled
        ? await buildIntegrityProof(
            encrypted.encryptedPayload,
            selectedSlate,
            encrypted.nonce,
            election.slate_set_hash,
          )
        : `development-pilot-proof-${encrypted.receiptHash}`;
      const response = await fetch(`${apiUrl}/api/v1/voter/elections/${election.election_id}/ballots`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({
          encrypted_payload: encrypted.encryptedPayload,
          receipt_hash: encrypted.receiptHash,
          zkp_proof: zkpProof,
          key_version: election.key_version,
          issuance_token: issuancePayload.issuance_token,
        }),
      });
      const payload = (await response.json()) as VoterBallotResponse & { detail?: string };
      if (!response.ok) {
        setMessage(payload.detail ?? "No se pudo registrar el voto.");
        return;
      }
      setReceipt(payload);
      setElection({ ...election, has_voted: true });
      setMessage("Voto cifrado registrado. Conserva el recibo para la prueba.");
    } catch {
      setMessage("No se pudo preparar o registrar el voto cifrado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="empty-state" aria-labelledby="voter-ballot-title">
      <span className="eyebrow">Emisión VOTER</span>
      <h2 id="voter-ballot-title">Emitir voto cifrado</h2>
      <p>
        El payload se cifra en el navegador y no incluye identidad. Se usa un token de emisión de un
        solo uso y prueba de integridad ballot-integrity-v1 cuando ZKP está habilitado.
      </p>
      {!sessionChecked ? (
        <p className="form-message">Comprobando la sesión del elector…</p>
      ) : !voterSessionReady ? (
        <>
          <p className="form-message">Debes solicitar y verificar un OTP antes de acceder a la boleta.</p>
          <Link className="button button-primary inline-button" href="/vote/login">
            Ir al acceso del elector
          </Link>
        </>
      ) : (
        <>
          <label htmlFor="voter-election-id">ID de elección</label>
          <input
            id="voter-election-id"
            value={electionId}
            onChange={(event) => setElectionId(event.target.value)}
            placeholder="UUID de la elección"
            required
          />
          <button className="button button-secondary" type="button" onClick={() => void loadElection()} disabled={busy || !electionId.trim()}>
            {busy ? "Cargando…" : "Cargar elección"}
          </button>
          {election ? (
            <>
              <h3>{election.title}</h3>
              {election.has_voted ? (
                <p className="form-message">Esta sesión ya registró un voto para esta elección.</p>
              ) : (
                <>
                  <label htmlFor="voter-slate">Selecciona una plancha</label>
                  <select id="voter-slate" value={selectedSlate} onChange={(event) => setSelectedSlate(event.target.value)}>
                    {election.slates.map((slate) => (
                      <option value={slate.id} key={slate.id}>{slate.name} · {slate.slogan ?? "Sin lema"}</option>
                    ))}
                  </select>
                  <button className="button button-primary" type="button" onClick={() => void castBallot()} disabled={busy || !selectedSlate}>
                    {busy ? "Cifrando…" : "Emitir voto"}
                  </button>
                </>
              )}
            </>
          ) : null}
        </>
      )}
      {receipt ? <p className="form-message">Recibo: {receipt.receipt_hash}</p> : null}
      {message ? <p className="form-message" role="status">{message}</p> : null}
    </section>
  );
}
