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
  slates: VoterSlate[];
};

type VoterBallotResponse = {
  accepted: boolean;
  receipt_hash: string;
  ballot_id: string;
  recorded_at: string;
};

function toBase64(value: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(value)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function toHex(value: ArrayBuffer): string {
  return Array.from(new Uint8Array(value), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function encryptSelection(
  election: VoterElection,
  slateId: string,
): Promise<{ encryptedPayload: string; receiptHash: string }> {
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
  const plaintext = new TextEncoder().encode(JSON.stringify({ slate_id: slateId }));
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
          zkp_proof: `development-pilot-proof-${encrypted.receiptHash}`,
          key_version: election.key_version,
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
      <span className="eyebrow">Piloto VOTER local</span>
      <h2 id="voter-ballot-title">Emitir voto de prueba</h2>
      <p>
        Esta pantalla requiere una sesión VOTER activa. El payload se cifra en el navegador y no incluye
        identidad; el backend enlaza la participación únicamente en MemberElectionStatus.
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
                    {busy ? "Cifrando…" : "Emitir voto de prueba"}
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
