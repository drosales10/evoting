"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { VoterBallotReceipt } from "@/components/voter/voter-ballot-receipt";

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
  qr_payload?: string;
};

type BallotBlocker =
  | "election_unavailable"
  | "not_authorized"
  | "already_voted"
  | null;

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
  const aesKey = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt"]);
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
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(encryptedPayload));
  return {
    encryptedPayload,
    receiptHash: toHex(digest),
    nonce,
  };
}

function mapLoadError(status: number, detail?: string): { blocker: BallotBlocker; message: string } {
  const normalized = (detail ?? "").toLowerCase();
  if (status === 403 || normalized.includes("not eligible") || normalized.includes("autoriz")) {
    return {
      blocker: "not_authorized",
      message: "No tiene autorización para votar en esta elección.",
    };
  }
  if (
    status === 409 ||
    normalized.includes("not accepting") ||
    normalized.includes("not accepting votes")
  ) {
    return {
      blocker: "election_unavailable",
      message: "La elección no está aceptando votos en este momento.",
    };
  }
  if (normalized.includes("already cast") || normalized.includes("ya registr")) {
    return {
      blocker: "already_voted",
      message: "Esta sesión ya registró su voto para esta elección.",
    };
  }
  return {
    blocker: null,
    message: detail ?? "No se pudo cargar la elección.",
  };
}

function blockerCopy(blocker: BallotBlocker): string | null {
  if (blocker === "election_unavailable") {
    return "La elección no está aceptando votos en este momento.";
  }
  if (blocker === "not_authorized") {
    return "No tiene autorización para votar en esta elección.";
  }
  if (blocker === "already_voted") {
    return "Esta sesión ya registró su voto para esta elección.";
  }
  return null;
}

export function VoterBallot() {
  const slateGroupId = useId();
  const [electionId, setElectionId] = useState("");
  const [election, setElection] = useState<VoterElection | null>(null);
  const [selectedSlate, setSelectedSlate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<VoterBallotResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [voterSessionReady, setVoterSessionReady] = useState(false);
  const [blocker, setBlocker] = useState<BallotBlocker>(null);

  useEffect(() => {
    setVoterSessionReady(Boolean(window.sessionStorage.getItem("evoting_voter_csrf")));
    setSessionChecked(true);
  }, []);

  const canEmit =
    Boolean(election) &&
    Boolean(selectedSlate) &&
    !busy &&
    !receipt &&
    !election?.has_voted &&
    blocker === null;

  async function loadElection() {
    setBusy(true);
    setMessage(null);
    setReceipt(null);
    setBlocker(null);
    setSelectedSlate("");
    setElection(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/v1/voter/elections/${electionId.trim()}`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json()) as VoterElection & { detail?: string };
      if (!response.ok) {
        const mapped = mapLoadError(response.status, payload.detail);
        setBlocker(mapped.blocker);
        setMessage(mapped.message);
        return;
      }
      setElection(payload);
      if (payload.has_voted) {
        setBlocker("already_voted");
        setMessage("Esta sesión ya registró su voto para esta elección.");
      }
    } catch {
      setMessage("No se pudo contactar la API VOTER.");
    } finally {
      setBusy(false);
    }
  }

  async function castBallot() {
    if (!election || !selectedSlate || election.has_voted || receipt) return;
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
        const mapped = mapLoadError(issuanceResponse.status, issuancePayload.detail);
        if (mapped.blocker) setBlocker(mapped.blocker);
        setMessage(mapped.message || (issuancePayload.detail ?? "No se pudo emitir el token de un solo uso."));
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
        const mapped = mapLoadError(response.status, payload.detail);
        if (mapped.blocker) setBlocker(mapped.blocker);
        setMessage(mapped.message || (payload.detail ?? "No se pudo registrar el voto."));
        return;
      }
      setReceipt(payload);
      setElection({ ...election, has_voted: true });
      setBlocker("already_voted");
      setSelectedSlate("");
    } catch {
      setMessage("No se pudo preparar o registrar el voto cifrado.");
    } finally {
      setBusy(false);
    }
  }

  if (!sessionChecked) {
    return (
      <section className="ballot-shell" aria-busy="true">
        <p className="ballot-muted">Comprobando la sesión del elector…</p>
      </section>
    );
  }

  if (!voterSessionReady) {
    return (
      <section className="ballot-shell" aria-labelledby="voter-ballot-title">
        <p className="ballot-eyebrow">Emisión VOTER</p>
        <h2 id="voter-ballot-title" className="ballot-title">
          Emitir voto cifrado
        </h2>
        <p className="ballot-muted">
          Debe solicitar y verificar un OTP antes de acceder a la papeleta. No se muestra identidad
          del elector en esta superficie.
        </p>
        <Link className="button button-primary inline-button" href="/vote/login">
          Ir al acceso del elector
        </Link>
      </section>
    );
  }

  if (receipt && election) {
    return (
      <section className="ballot-shell ballot-shell--confirm" aria-labelledby="voter-confirm-title">
        <p className="ballot-status-pill ballot-status-pill--ok">
          <span aria-hidden="true">●</span> Elección abierta
        </p>
        <h2 id="voter-confirm-title" className="ballot-title">
          Voto cifrado registrado
        </h2>
        <p className="ballot-lead">
          Su voto fue aceptado correctamente. Esta sesión ya registró su voto para esta elección.
        </p>

        <VoterBallotReceipt
          receipt={{
            electionTitle: election.title,
            electionId: election.election_id,
            ballotId: receipt.ballot_id,
            receiptHash: receipt.receipt_hash,
            recordedAt: receipt.recorded_at,
            keyVersion: election.key_version,
            qrPayload: receipt.qr_payload,
          }}
        />

        <p className="ballot-help">
          Conserve este recibo para fines de verificación. El recibo no revela el contenido de su
          voto.
        </p>
        <Link className="ballot-help-link" href="/vote/login">
          Necesito ayuda
        </Link>
      </section>
    );
  }

  const activeBlockerMessage = blockerCopy(blocker) ?? message;
  const emissionDisabled = !canEmit || blocker !== null || Boolean(election?.has_voted);

  return (
    <section className="ballot-shell" aria-labelledby="voter-ballot-title">
      <p className="ballot-eyebrow">Emisión VOTER</p>
      <h2 id="voter-ballot-title" className="ballot-title">
        Emitir voto cifrado
      </h2>

      {!election ? (
        <div className="ballot-load">
          <p className="ballot-muted">
            Indique el identificador de la elección para cargar la papeleta. Su identidad no forma
            parte de esta pantalla.
          </p>
          <label className="ballot-field-label" htmlFor="voter-election-id">
            ID de elección
          </label>
          <input
            id="voter-election-id"
            className="input-field"
            value={electionId}
            onChange={(event) => setElectionId(event.target.value)}
            placeholder="UUID de la elección"
            autoComplete="off"
            required
          />
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void loadElection()}
            disabled={busy || !electionId.trim()}
          >
            {busy ? "Cargando…" : "Cargar elección"}
          </button>
          {activeBlockerMessage ? (
            <p className="ballot-alert" role="status">
              {activeBlockerMessage}
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <p className="ballot-election-name">{election.title}</p>
          <div className="ballot-chips" aria-label="Estado de la elección">
            <span className="ballot-chip ballot-chip--active">Elección activa</span>
            <span className="ballot-chip ballot-chip--open">Votación abierta</span>
          </div>

          <ul className="ballot-info-list">
            <li>
              Seleccione una plancha. Los candidatos asociados se muestran como información de la
              plancha seleccionada.
            </li>
            <li>Su voto se cifra en el navegador y no se almacena junto con su identidad.</li>
            <li>Solo puede emitir un voto para esta elección.</li>
          </ul>

          {blocker || election.has_voted ? (
            <div className="ballot-blocker" role="status">
              <p>{activeBlockerMessage ?? "Esta sesión ya registró su voto para esta elección."}</p>
            </div>
          ) : (
            <>
              <h3 className="ballot-section-title">Seleccione una plancha</h3>
              <div className="ballot-slate-grid" role="radiogroup" aria-labelledby={`${slateGroupId}-label`}>
                <span id={`${slateGroupId}-label`} className="sr-only">
                  Planchas disponibles
                </span>
                {election.slates.map((slate) => {
                  const selected = selectedSlate === slate.id;
                  return (
                    <label
                      key={slate.id}
                      className={`ballot-slate-card${selected ? " is-selected" : ""}`}
                    >
                      <div className="ballot-slate-card__body">
                        <p className="ballot-slate-card__name">{slate.name}</p>
                        <p className="ballot-slate-card__slogan">{slate.slogan ?? "Sin lema"}</p>
                        <ul className="ballot-slate-card__candidates">
                          {slate.candidates.length === 0 ? (
                            <li>Sin candidatos registrados</li>
                          ) : (
                            slate.candidates.map((candidate) => (
                              <li key={candidate.id}>
                                {candidate.position_title} — {candidate.member_full_name}
                              </li>
                            ))
                          )}
                        </ul>
                      </div>
                      <div className="ballot-slate-card__footer">
                        <input
                          type="radio"
                          name="voter-slate"
                          value={slate.id}
                          checked={selected}
                          onChange={() => setSelectedSlate(slate.id)}
                        />
                        <span className="ballot-slate-card__select-label">
                          {selected ? "Plancha seleccionada" : "Seleccionar"}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </>
          )}

          <div className="ballot-actions">
            <button
              className="button button-primary ballot-emit-btn"
              type="button"
              onClick={() => void castBallot()}
              disabled={emissionDisabled}
            >
              {busy ? "Cifrando…" : "Emitir voto"}
            </button>
            <p className="ballot-help">
              La emisión utiliza un token de un solo uso para proteger la operación.
            </p>
            <Link className="ballot-help-link" href="/vote/login">
              Necesito ayuda
            </Link>
          </div>

          {message && !blocker && !election.has_voted ? (
            <p className="ballot-alert" role="status">
              {message}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
