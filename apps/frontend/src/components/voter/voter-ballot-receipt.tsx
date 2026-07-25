"use client";

import { useRef } from "react";

export type BallotReceiptData = {
  electionTitle: string;
  electionId: string;
  ballotId: string;
  receiptHash: string;
  recordedAt: string;
  keyVersion?: string;
};

function formatDateTime(iso: string): { fecha: string; hora: string } {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return { fecha: "—", hora: "—" };
  }
  return {
    fecha: new Intl.DateTimeFormat("es-VE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      timeZone: "UTC",
    }).format(date),
    hora: new Intl.DateTimeFormat("es-VE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }).format(date),
  };
}

function shortRef(value: string, size = 8): string {
  return value.replace(/-/g, "").slice(0, size).toUpperCase();
}

type VoterBallotReceiptProps = {
  receipt: BallotReceiptData;
};

export function VoterBallotReceipt({ receipt }: VoterBallotReceiptProps) {
  const ticketRef = useRef<HTMLElement>(null);
  const { fecha, hora } = formatDateTime(receipt.recordedAt);
  const electionRef = shortRef(receipt.electionId);
  const ballotRef = shortRef(receipt.ballotId, 12);
  const verificationId = receipt.receiptHash.toLowerCase();

  function handlePrint() {
    const node = ticketRef.current;
    if (!node) return;
    const printWindow = window.open("", "_blank", "noopener,noreferrer,width=420,height=720");
    if (!printWindow) return;
    printWindow.document.write(`<!DOCTYPE html><html lang="es"><head><meta charset="utf-8" />
<title>Recibo de verificación — eVoting</title>
<style>
  @page { size: 80mm auto; margin: 4mm; }
  body { margin: 0; font-family: "Courier New", Courier, monospace; color: #111; background: #fff; }
  .ballot-fiscal-ticket { width: 72mm; margin: 0 auto; padding: 10px 8px; border: 1px dashed #222; }
  .ballot-fiscal-ticket__head { text-align: center; }
  .ballot-fiscal-ticket__brand { margin: 0; font-size: 16px; font-weight: 700; }
  .ballot-fiscal-ticket__title { margin: 6px 0 0; font-size: 12px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
  .ballot-fiscal-ticket__sub { margin: 4px 0 0; font-size: 11px; color: #444; }
  .ballot-fiscal-ticket__rule { border: none; border-top: 1px dashed #222; margin: 10px 0; }
  .ballot-fiscal-ticket__rows { margin: 0; padding: 0; }
  .ballot-fiscal-ticket__row { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; margin: 4px 0; }
  .ballot-fiscal-ticket__row dt { color: #333; }
  .ballot-fiscal-ticket__row dd { margin: 0; font-weight: 700; text-align: right; max-width: 60%; word-break: break-word; }
  .ballot-fiscal-ticket__label { margin: 0; font-size: 10px; font-weight: 700; text-transform: uppercase; color: #444; }
  .ballot-fiscal-ticket__hash { margin: 6px 0 0; font-size: 10px; line-height: 1.35; word-break: break-all; }
  .ballot-fiscal-ticket__notice { margin: 0; text-align: center; font-size: 11px; font-weight: 700; }
  .ballot-fiscal-ticket__fine { margin: 8px 0 0; text-align: center; font-size: 10px; color: #444; line-height: 1.35; }
  .ballot-receipt-actions { display: none; }
</style></head><body>${node.outerHTML}
<script>window.onload=function(){window.focus();window.print();}</script></body></html>`);
    printWindow.document.close();
  }

  return (
    <div className="ballot-receipt-wrap">
      <article ref={ticketRef} className="ballot-fiscal-ticket" aria-label="Recibo de verificación">
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
            <dt>Fecha (UTC)</dt>
            <dd>{fecha}</dd>
          </div>
          <div className="ballot-fiscal-ticket__row">
            <dt>Hora (UTC)</dt>
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

      <div className="ballot-receipt-actions">
        <button className="button button-secondary" type="button" onClick={handlePrint}>
          Imprimir recibo
        </button>
      </div>
    </div>
  );
}
