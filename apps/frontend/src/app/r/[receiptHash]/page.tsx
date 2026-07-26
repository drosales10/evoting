import { redirect, notFound } from "next/navigation";

type PageProps = {
  params: Promise<{ receiptHash: string }>;
};

/** Ruta corta para QR: /r/{hash64} → /recibo/{hash64} */
export default async function ShortReceiptRedirectPage({ params }: PageProps) {
  const { receiptHash } = await params;
  const hash = receiptHash?.trim().toLowerCase() ?? "";
  if (hash.length !== 64 || !/^[0-9a-f]+$/.test(hash)) {
    notFound();
  }
  redirect(`/recibo/${hash}`);
}
