/**
 * Helpers de autenticación ADMIN (cookies HttpOnly + CSRF en sessionStorage).
 */

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RefreshPayload = {
  status?: string;
  csrf_token?: string | null;
  detail?: string;
};

let refreshInFlight: Promise<boolean> | null = null;

/** Renueva access cookie vía refresh (path /api/v1/auth). Actualiza CSRF si viene en la respuesta. */
export async function refreshAdminSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${apiUrl()}/api/v1/auth/admin/refresh`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) return false;
      const payload = (await response.json()) as RefreshPayload;
      if (payload.csrf_token) {
        window.sessionStorage.setItem("evoting_admin_csrf", payload.csrf_token);
      }
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export function getAdminCsrfToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem("evoting_admin_csrf");
}

/**
 * fetch con credentials. Si recibe 401, intenta refresh una vez y reintenta.
 */
export async function adminFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const csrf = getAdminCsrfToken();
  if (csrf && !headers.has("X-CSRF-Token") && init.method && init.method.toUpperCase() !== "GET") {
    headers.set("X-CSRF-Token", csrf);
  }

  const first = await fetch(input, {
    ...init,
    credentials: "include",
    headers,
  });

  if (first.status !== 401) return first;

  const refreshed = await refreshAdminSession();
  if (!refreshed) return first;

  const retryHeaders = new Headers(init.headers);
  const nextCsrf = getAdminCsrfToken();
  if (nextCsrf && init.method && init.method.toUpperCase() !== "GET") {
    retryHeaders.set("X-CSRF-Token", nextCsrf);
  }

  return fetch(input, {
    ...init,
    credentials: "include",
    headers: retryHeaders,
  });
}
