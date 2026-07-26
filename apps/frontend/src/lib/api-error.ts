/**
 * Normaliza `detail` de FastAPI / Pydantic a un string seguro para React.
 * Cubre: string, array de ValidationError {type,loc,msg,input,ctx}, y objetos con msg.
 */

type ValidationIssue = {
  loc?: unknown;
  msg?: unknown;
};

function formatLoc(loc: unknown): string | null {
  if (!Array.isArray(loc) || loc.length === 0) {
    return null;
  }
  const parts = loc.filter(
    (part): part is string | number => typeof part === "string" || typeof part === "number",
  );
  // Omite el prefijo "body" típico de FastAPI para mensajes más legibles.
  const useful = parts[0] === "body" ? parts.slice(1) : parts;
  return useful.length > 0 ? useful.join(".") : null;
}

function formatValidationIssue(issue: unknown): string[] {
  if (typeof issue === "string" && issue.trim()) {
    return [issue.trim()];
  }
  if (typeof issue !== "object" || issue === null) {
    return [];
  }
  const validationIssue = issue as ValidationIssue;
  const message = typeof validationIssue.msg === "string" ? validationIssue.msg.trim() : "";
  if (!message) {
    return [];
  }
  const location = formatLoc(validationIssue.loc);
  return [location ? `${location}: ${message}` : message];
}

/** Extrae un mensaje legible desde `detail` crudo (puede ser string, array u objeto). */
export function formatApiDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(formatValidationIssue);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  if (typeof detail === "object" && detail !== null) {
    const messages = formatValidationIssue(detail);
    if (messages.length > 0) {
      return messages[0] ?? null;
    }
  }
  return null;
}

/** Lee `payload.detail` y siempre devuelve un string (nunca un objeto). */
export function formatApiError(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return fallback;
  }
  return formatApiDetail((payload as { detail: unknown }).detail) ?? fallback;
}

/** Mensaje por status HTTP habituales de auth/API, con fallback a detail normalizado. */
export function formatHttpApiError(
  status: number,
  payload: unknown,
  fallback: string,
): string {
  const detail = formatApiError(payload, "");
  if (status === 401) {
    return detail || "No autorizado. Verifica tus credenciales o vuelve a iniciar sesión.";
  }
  if (status === 403) {
    return detail || "No tienes permiso para esta acción.";
  }
  if (status === 422) {
    return detail || "Los datos enviados no son válidos. Revisa el formulario.";
  }
  return detail || fallback;
}
