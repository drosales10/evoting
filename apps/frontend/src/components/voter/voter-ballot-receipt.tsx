"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { APP_TIMEZONE, formatAppDate, formatAppTime } from "@/lib/datetime";

export type BallotReceiptData = {
  electionTitle: string;
  electionId: string;
  ballotId: string;
  receiptHash: string;
  recordedAt: string;
  keyVersion?: string;
  qrPayload?: string | null;
};

function shortRef(value: string, size = 8): string {
  return value.replace(/-/g, "").slice(0, size).toUpperCase();
}

function resolveQrModule(mod: unknown): {
  toDataURL: (
    text: string,
    options?: Record<string, unknown>,
  ) => Promise<string>;
} {
  const candidate = mod as {
    toDataURL?: (text: string, options?: Record<string, unknown>) => Promise<string>;
    default?: {
      toDataURL?: (text: string, options?: Record<string, unknown>) => Promise<string>;
    };
  };
  const api = candidate.toDataURL ? candidate : candidate.default;
  if (!api?.toDataURL) {
    throw new Error("Módulo qrcode sin toDataURL");
  }
  return api as {
    toDataURL: (
      text: string,
      options?: Record<string, unknown>,
    ) => Promise<string>;
  };
}

/** URL corta y estable para el QR (menos módulos = mejor lectura). */
function buildVerificationUrl(receiptHash: string, apiPayload?: string | null): string {
  const hash = receiptHash.toLowerCase();
  const fromApi = apiPayload?.trim();
  if (typeof window === "undefined") {
    return fromApi || `/r/${hash}`;
  }
  // Preferir ruta corta /r/{hash} en el origen actual (escaneable).
  // Si la API trae otra URL del mismo host, igual usamos /r/ para densificar el QR.
  try {
    if (fromApi) {
      const parsed = new URL(fromApi, window.location.origin);
      if (parsed.origin === window.location.origin) {
        return `${window.location.origin}/r/${hash}`;
      }
      return fromApi;
    }
  } catch {
    /* ignore */
  }
  return `${window.location.origin}/r/${hash}`;
}

type VoterBallotReceiptProps = {
  receipt: BallotReceiptData;
};

export function VoterBallotReceipt({ receipt }: VoterBallotReceiptProps) {
  const ticketRef = useRef<HTMLElement>(null);
  const [printMessage, setPrintMessage] = useState<string | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const fecha = formatAppDate(receipt.recordedAt);
  const hora = formatAppTime(receipt.recordedAt);
  const electionRef = shortRef(receipt.electionId);
  const ballotRef = shortRef(receipt.ballotId, 12);
  const verificationId = receipt.receiptHash.toLowerCase();
  const [qrPayload, setQrPayload] = useState(() =>
    buildVerificationUrl(verificationId, receipt.qrPayload),
  );

  useEffect(() => {
    setQrPayload(buildVerificationUrl(verificationId, receipt.qrPayload));
  }, [receipt.qrPayload, verificationId]);

  useEffect(() => {
    if (!qrPayload) {
      setQrDataUrl(null);
      return;
    }
    let cancelled = false;
    setQrError(null);
    void import("qrcode")
      .then((mod) => {
        const QRCode = resolveQrModule(mod);
        return QRCode.toDataURL(qrPayload, {
          width: 320,
          margin: 4,
          errorCorrectionLevel: "H",
          type: "image/png",
          color: { dark: "#000000", light: "#ffffff" },
        });
      })
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setQrDataUrl(null);
          setQrError(error instanceof Error ? error.message : "No se pudo generar el QR");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [qrPayload]);

  const handleDownloadQr = useCallback(() => {
    if (!qrDataUrl) return;
    const anchor = document.createElement("a");
    anchor.href = qrDataUrl;
    anchor.download = `evoting-recibo-${verificationId.slice(0, 12)}.png`;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }, [qrDataUrl, verificationId]);

  const handlePrint = useCallback(() => {
    setPrintMessage(null);
    const node = ticketRef.current;
    if (!node) {
      setPrintMessage("No se encontró el recibo para imprimir.");
      return;
    }

    document.body.classList.add("printing-ballot-receipt");
    const cleanup = () => {
      document.body.classList.remove("printing-ballot-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.setTimeout(cleanup, 60_000);

    try {
      window.print();
    } catch {
      cleanup();
      setPrintMessage("No se pudo abrir el diálogo de impresión. Pruebe Ctrl+P / Cmd+P.");
    }
  }, []);

  return (
    <div className="ballot-receipt-wrap">
      <article
        ref={ticketRef}
        className="ballot-fiscal-ticket"
        id="ballot-receipt-print-root"
        aria-label="Recibo de verificación"
      >
        <header className="ballot-fiscal-ticket__head">
          <p className="ballot-fiscal-ticket__brand">eVoting</p>
          <p className="ballot-fiscal-ticket__title">Recibo de verificación</p>
          <p className="ballot-fiscal-ticket__sub">Papeleta electrónica · canal web</p>
        </header>

        <hr className="ballot-fiscal-ticket__rule" />

        <dl className="ballot-fiscal-ticket__rows">
          <div className="ballot-fiscal-ticket__row">
            <dt>Elección</dt>
            <dd>{receipt.electionTitle}</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>Ref. elección</dt>
            <dd>{electionRef}</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>ID papeleta</dt>
            <dd>{ballotRef}</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>Ubicación</dt>
            <dd>Emisión web · sesión VOTER</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>Fecha ({APP_TIMEZONE})</dt>
            <dd>{fecha}</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>Hora ({APP_TIMEZONE})</dt>
            <dd>{hora}</dd>
          </div>
          {receipt.keyVersion ? (
            <div className="ballot-fiscal-ticket__row">
              <dt>Clave cifrado</dt>
              <dd>{receipt.keyVersion}</dd>
            </div>
          ) : null}
          <div className="ballot-fiscal-ticket__row">
            <dt>Estado</dt>
            <dd>ACEPTADO</dd>
          </div>
        </dl>

        <hr className="ballot-fiscal-ticket__rule" />

        <p className="ballot-fiscal-ticket__label">ID del recibo de verificación</p>
        <p className="ballot-fiscal-ticket__hash">{verificationId}</p>

        <hr className="ballot-fiscal-ticket__rule" />

        <p className="ballot-fiscal-ticket__notice">
          Esta sesión ya registró su voto para esta elección.
        </p>
        <p className="ballot-fiscal-ticket__fine">
          Conserve este recibo para fines de verificación. El recibo no revela el contenido de su
          voto.
        </p>

        {qrPayload ? (
          <div className="ballot-fiscal-ticket__qr">
            {qrDataUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="ballot-fiscal-ticket__qr-img"
                src={qrDataUrl}
                alt="Código QR de verificación de existencia del recibo"
                width={320}
                height={320}
              />
            ) : (
              <p className="ballot-fiscal-ticket__fine">
                {qrError ? `Error QR: ${qrError}` : "Generando código QR…"}
              </p>
            )}
            <p className="ballot-fiscal-ticket__qr-caption">Escanee para verificar existencia</p>
            <a className="ballot-fiscal-ticket__qr-link break-all" href={qrPayload}>
              {qrPayload}
            </a>
          </div>
        ) : null}

        <p className="ballot-fiscal-ticket__fine center">*** Fin del comprobante ***</p>
      </article>

      <div className="ballot-receipt-actions no-print">
        <button className="button button-secondary" type="button" onClick={handlePrint}>
          Imprimir recibo
        </button>
        <button
          className="button button-secondary"
          type="button"
          onClick={handleDownloadQr}
          disabled={!qrDataUrl}
        >
          Descargar QR (PNG)
        </button>
        {printMessage ? (
          <p className="mt-2 text-center text-sm text-amber-800 dark:text-amber-200" role="status">
            {printMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
