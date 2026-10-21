const configuredApiOrigin = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/**
 * Base para el navegador. Vacía a propósito: `/api` sale del mismo host
 * (rewrite de Next en local, nginx en producción) y no depende de CORS.
 */
export function clientApiBase(): string {
  return "";
}

const jsonCache = new Map<string, { expires: number; value: unknown }>();
const jsonInflight = new Map<string, Promise<unknown>>();

export function invalidateCachedJson(prefix = ""): void {
  for (const key of jsonCache.keys()) {
    if (!prefix || key.startsWith(prefix)) jsonCache.delete(key);
  }
}

/** Comparte la petición en curso y, si ttlMs > 0, reutiliza el JSON un rato. */
export async function shareJson<T>(
  key: string,
  ttlMs: number,
  load: () => Promise<T | null>,
): Promise<T | null> {
  const hit = jsonCache.get(key);
  if (ttlMs > 0 && hit && hit.expires > Date.now()) return hit.value as T;
  const pending = jsonInflight.get(key);
  if (pending) return pending as Promise<T | null>;
  const run = load()
    .then((value) => {
      if (ttlMs > 0 && value !== null) {
        jsonCache.set(key, { expires: Date.now() + ttlMs, value });
      }
      return value;
    })
    .finally(() => {
      jsonInflight.delete(key);
    });
  jsonInflight.set(key, run);
  return run;
}

export const TERRITORY_CACHE_MS = 60_000;

export async function fetchAdminJson<T>(path: string, ttlMs = 0): Promise<T | null> {
  return shareJson(path, ttlMs, async () => {
    try {
      const response = await fetch(`${clientApiBase()}${path}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) return null;
      return (await response.json()) as T;
    } catch {
      return null;
    }
  });
}

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
