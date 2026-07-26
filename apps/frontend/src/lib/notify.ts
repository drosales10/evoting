import { toast } from "sonner";

import { formatApiError, formatHttpApiError } from "@/lib/api-error";

type NotifyOptions = {
  description?: string;
  duration?: number;
};

/** API fina sobre Sonner + normalización de errores FastAPI. */
export const notify = {
  success(message: string, options?: NotifyOptions) {
    return toast.success(message, options);
  },
  error(message: string, options?: NotifyOptions) {
    return toast.error(message, options);
  },
  info(message: string, options?: NotifyOptions) {
    return toast.info(message, options);
  },
  warning(message: string, options?: NotifyOptions) {
    return toast.warning(message, options);
  },
  /** Usa `payload.detail` (string o ValidationError[]) de forma segura. */
  apiError(payload: unknown, fallback: string, options?: NotifyOptions) {
    return toast.error(formatApiError(payload, fallback), options);
  },
  /** Mensajes tipados por HTTP 401/403/422 + detail normalizado. */
  httpError(
    status: number,
    payload: unknown,
    fallback: string,
    options?: NotifyOptions,
  ) {
    return toast.error(formatHttpApiError(status, payload, fallback), options);
  },
};
