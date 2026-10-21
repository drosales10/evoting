/**
 * Sobre RSA-OAEP-256 / AES-256-GCM compartido por la papeleta de plancha
 * y la boleta del estatuto. El plaintext de la elección no cambia.
 */

export function toBase64Url(value: ArrayBuffer | Uint8Array): string {
  const bytes = value instanceof Uint8Array ? value : new Uint8Array(value);
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

export function toHex(value: ArrayBuffer): string {
  return Array.from(new Uint8Array(value), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return toHex(digest);
}

export function randomNonceHex(): string {
  const nonceBytes = crypto.getRandomValues(new Uint8Array(16));
  return toHex(nonceBytes.buffer);
}

export async function sealPlaintext(
  publicKeyPem: string,
  plaintextJson: string,
  keyVersion: string,
): Promise<{ encryptedPayload: string; receiptHash: string }> {
  const publicKeyData = publicKeyPem
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
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    aesKey,
    new TextEncoder().encode(plaintextJson),
  );
  const rawAesKey = await crypto.subtle.exportKey("raw", aesKey);
  const wrappedKey = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, publicKey, rawAesKey);
  const encryptedPayload = JSON.stringify({
    algorithm: "RSA-OAEP-256/AES-256-GCM",
    wrapped_key: toBase64Url(wrappedKey),
    iv: toBase64Url(iv.buffer),
    ciphertext: toBase64Url(ciphertext),
    key_version: keyVersion,
  });
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(encryptedPayload));
  return { encryptedPayload, receiptHash: toHex(digest) };
}

export async function buildSlateIntegrityProof(
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
  return toBase64Url(new TextEncoder().encode(proof));
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value) ?? "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
    .join(",")}}`;
}

export type StatuteDecision = {
  article_id: string;
  approved: boolean;
  comment?: string | null;
};

/** Mismo JSON canónico que canonical_statute_plaintext en el backend. */
export function canonicalStatutePlaintext(decisions: StatuteDecision[], nonce: string): string {
  const rows = decisions
    .map((item) => {
      const row: Record<string, boolean | string> = {
        approved: item.approved,
        article_id: item.article_id.toLowerCase(),
      };
      if (!item.approved) {
        row.comment = (item.comment ?? "").trim();
      }
      return row;
    })
    .sort((left, right) => String(left.article_id).localeCompare(String(right.article_id)));
  return stableStringify({ decisions: rows, nonce });
}

export async function buildStatuteIntegrityProof(
  encryptedPayload: string,
  plaintext: string,
  articleSetHash: string,
): Promise<string> {
  const commitment = await sha256Hex(plaintext);
  const payloadBinding = await sha256Hex(`${encryptedPayload}:${commitment}`);
  const proof = JSON.stringify({
    version: "statute-integrity-v1",
    commitment,
    payload_binding: payloadBinding,
    article_set_hash: articleSetHash,
  });
  return toBase64Url(new TextEncoder().encode(proof));
}
