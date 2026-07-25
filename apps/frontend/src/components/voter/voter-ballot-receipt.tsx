"use client";

import { useCallback, useRef, useState } from "react";

import { APP_TIMEZONE, formatAppDate, formatAppTime } from "@/lib/datetime";

export type BallotReceiptData = {
  electionTitle: string;
  electionId: string;
  ballotId: string;
  receiptHash: string;
  recordedAt: string;
  keyVersion?: string;
};

function shortRef(value: string, size = 8): string {
  return value.replace(/-/g, "").slice(0, size).toUpperCase();
}

type VoterBallotReceiptProps = {
  receipt: BallotReceiptData;
};

export function VoterBallotReceipt({ receipt }: VoterBallotReceiptProps) {
  const ticketRef = useRef<HTMLElement>(null);
  const [printMessage, setPrintMessage] = useState<string | null>(null);
  const fecha = formatAppDate(receipt.recordedAt);
  const hora = formatAppTime(receipt.recordedAt);
  const electionRef = shortRef(receipt.electionId);
  const ballotRef = shortRef(receipt.ballotId, 12);
  const verificationId = receipt.receiptHash.toLowerCase();

  const handlePrint = useCallback(() => {
    setPrintMessage(null);
    const node = ticketRef.current;
    if (!node) {
      setPrintMessage("No se encontró el recibo para imprimir.");
      return;
    }

    // Preferir impresión de la página actual (evita popup blockers / noopener = null).
    document.body.classList.add("printing-ballot-receipt");
    const cleanup = () => {
      document.body.classList.remove("printing-ballot-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);

    // Safari / algunos motores no disparan afterprint de forma fiable.
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
        <p className="ballot-fiscal-ticket__fine center">*** Fin del comprobante ***</p>
      </article>

      <div className="ballot-receipt-actions no-print">
        <button className="button button-secondary" type="button" onClick={handlePrint}>
          Imprimir recibo
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
