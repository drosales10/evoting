/**
 * Zona horaria de la aplicación (display + interpretación de datetime-local).
 * Configurable con NEXT_PUBLIC_APP_TIMEZONE (default America/Caracas).
 */

export const APP_TIMEZONE =
  process.env.NEXT_PUBLIC_APP_TIMEZONE?.trim() || "America/Caracas";

export const APP_LOCALE = process.env.NEXT_PUBLIC_APP_LOCALE?.trim() || "es-VE";

export function formatAppDateTime(
  value: string | Date,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(APP_LOCALE, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: APP_TIMEZONE,
    ...options,
  }).format(date);
}

export function formatAppDate(value: string | Date): string {
  return formatAppDateTime(value, { dateStyle: "medium", timeStyle: undefined });
}

export function formatAppTime(value: string | Date): string {
  return formatAppDateTime(value, {
    dateStyle: undefined,
    timeStyle: "medium",
    hour12: false,
  });
}

type ZonedParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
};

function getZonedParts(date: Date, timeZone: string): ZonedParts {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const read = (type: Intl.DateTimeFormatPartTypes) => {
    const raw = parts.find((part) => part.type === type)?.value ?? "0";
    // Intl may emit "24" for midnight in some engines; normalize to 0.
    if (type === "hour" && raw === "24") return 0;
    return Number(raw);
  };

  return {
    year: read("year"),
    month: read("month"),
    day: read("day"),
    hour: read("hour"),
    minute: read("minute"),
    second: read("second"),
  };
}

/**
 * Interpreta un valor `datetime-local` (sin zona) como reloj de pared en APP_TIMEZONE
 * y lo convierte a ISO UTC.
 */
export function datetimeLocalToUtcIso(
  localValue: string,
  timeZone: string = APP_TIMEZONE,
): string {
  const trimmed = localValue.trim();
  if (!trimmed) {
    throw new Error("Fecha/hora vacía");
  }
  const match = trimmed.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/,
  );
  if (!match) {
    // Fallback: deja que Date intente parsear (p. ej. ya viene con offset).
    const fallback = new Date(trimmed);
    if (Number.isNaN(fallback.getTime())) {
      throw new Error(`Fecha/hora inválida: ${localValue}`);
    }
    return fallback.toISOString();
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6] ?? "0");

  // Aproximación UTC y corrección iterativa al offset de la zona.
  let utcMillis = Date.UTC(year, month - 1, day, hour, minute, second);
  for (let i = 0; i < 3; i += 1) {
    const asUtc = new Date(utcMillis);
    const zoned = getZonedParts(asUtc, timeZone);
    const asIfUtc = Date.UTC(
      zoned.year,
      zoned.month - 1,
      zoned.day,
      zoned.hour,
      zoned.minute,
      zoned.second,
    );
    const desired = Date.UTC(year, month - 1, day, hour, minute, second);
    utcMillis += desired - asIfUtc;
  }
  return new Date(utcMillis).toISOString();
}

/** Convierte un ISO UTC a valor para input datetime-local en APP_TIMEZONE. */
export function utcIsoToDatetimeLocal(
  iso: string,
  timeZone: string = APP_TIMEZONE,
): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const zoned = getZonedParts(date, timeZone);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${zoned.year}-${pad(zoned.month)}-${pad(zoned.day)}T${pad(zoned.hour)}:${pad(zoned.minute)}`;
}
