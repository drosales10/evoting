const configuredApiOrigin = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/**
 * En el navegador, las rutas de la API se piden al mismo origen.
 * Next las reescribe hacia el backend y así no dependen de CORS ni del host de la página.
 */
export function sameOriginApi(input: string): string {
  if (typeof window === "undefined") return input;
  try {
    const url = new URL(input, window.location.origin);
    const api = new URL(configuredApiOrigin());
    if (url.origin === api.origin) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
  } catch {
    return input;
  }
  return input;
}

export function unreachableApiResponse(): Response {
  return new Response(JSON.stringify({ detail: "No se pudo contactar la API." }), {
    status: 503,
    headers: { "Content-Type": "application/json" },
  });
}
