/* Error classification shared by the API client and UI error states. */


export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;
  constructor(message: string, code: string, status: number, retryable = false) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

export const ERROR_CLASSIFICATIONS: Record<string, { message: string; retryable: boolean }> = {
  OFFLINE:            { message: "ResearchSwarm is temporarily unavailable. Please try again in a few minutes.", retryable: true },
  CORS_ERROR:         { message: "Unable to connect to the backend service. Please contact support.", retryable: false },
  DNS_ERROR:          { message: "Unable to resolve the backend server address. Check your internet connection.", retryable: true },
  NETWORK_OFFLINE:    { message: "You're currently offline. Please check your internet connection.", retryable: true },
  TIMEOUT:            { message: "The request took too long. Please try again.", retryable: true },
  UNAUTHORIZED:       { message: "The email or password is incorrect.", retryable: false },
  FORBIDDEN:          { message: "You do not have permission to perform this action.", retryable: false },
  NOT_FOUND:          { message: "The requested resource was not found.", retryable: false },
  RATE_LIMITED:       { message: "Too many login attempts. Please wait a few minutes.", retryable: true },
  VALIDATION_ERROR:   { message: "Please check your input and try again.", retryable: false },
  ORGANIZATION_REQUIRED: { message: "Finish setting up your workspace.", retryable: false },
  INTERNAL_ERROR:     { message: "Something went wrong while processing your request. Our team has been notified.", retryable: true },
  ABORTED:            { message: "Request was cancelled.", retryable: false },
  UNKNOWN:            { message: "An unexpected error occurred. Please try again.", retryable: true },
};

export function classifyError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  if (e instanceof DOMException && e.name === "AbortError") {
    return new ApiError(ERROR_CLASSIFICATIONS.ABORTED.message, "ABORTED", 0, false);
  }
  if (e instanceof TypeError) {
    const msg = e.message.toLowerCase();
    // CORS errors — distinct from network offline
    if (msg.includes("cors") || msg.includes("cross-origin")) {
      return new ApiError(ERROR_CLASSIFICATIONS.CORS_ERROR.message, "CORS_ERROR", 0, false);
    }
    // DNS / name resolution failure
    if (msg.includes("enotfound") || msg.includes("dns") || msg.includes("name not resolved") || msg.includes("getaddrinfo")) {
      return new ApiError(ERROR_CLASSIFICATIONS.DNS_ERROR.message, "DNS_ERROR", 0, true);
    }
    // Network offline (no internet connection)
    if (msg.includes("network") || msg.includes("networkerror") || msg.includes("err_network")) {
      return new ApiError(ERROR_CLASSIFICATIONS.NETWORK_OFFLINE.message, "NETWORK_OFFLINE", 0, true);
    }
    // fetch failure (server unreachable)
    if (msg.includes("fetch") || msg.includes("failed to fetch")) {
      return new ApiError(ERROR_CLASSIFICATIONS.OFFLINE.message, "OFFLINE", 0, true);
    }
    return new ApiError(ERROR_CLASSIFICATIONS.OFFLINE.message, "OFFLINE", 0, true);
  }
  if (e instanceof Error) {
    return new ApiError(e.message, "UNKNOWN", 0, true);
  }
  return new ApiError(ERROR_CLASSIFICATIONS.UNKNOWN.message, "UNKNOWN", 0, true);
}

export function classifyResponse(status: number, body: Record<string, unknown>): ApiError {
  const code = typeof body.code === "string" ? body.code : typeof (body.detail as Record<string, unknown>)?.code === "string" ? (body.detail as Record<string, unknown>).code as string : "";
  const detailRaw = (body.detail as Record<string, unknown>)?.message || body.detail || body.message || body.error || "";
  const detail = typeof detailRaw === "string" ? detailRaw : String(detailRaw);

  if (status === 401) return new ApiError(ERROR_CLASSIFICATIONS.UNAUTHORIZED.message, "UNAUTHORIZED", status, false);
  if (status === 403) {
    if (code === "organization_required") {
      return new ApiError(ERROR_CLASSIFICATIONS.ORGANIZATION_REQUIRED.message, "ORGANIZATION_REQUIRED", status, false);
    }
    return new ApiError(ERROR_CLASSIFICATIONS.FORBIDDEN.message, "FORBIDDEN", status, false);
  }
  if (status === 404) return new ApiError(detail || ERROR_CLASSIFICATIONS.NOT_FOUND.message, "NOT_FOUND", status, false);
  if (status === 429) return new ApiError(ERROR_CLASSIFICATIONS.RATE_LIMITED.message, "RATE_LIMITED", status, true);
  if (status === 422) return new ApiError(detail || ERROR_CLASSIFICATIONS.VALIDATION_ERROR.message, "VALIDATION_ERROR", status, false);
  if (status >= 500) return new ApiError(detail || ERROR_CLASSIFICATIONS.INTERNAL_ERROR.message, "INTERNAL_ERROR", status, true);
  return new ApiError(detail || `Request failed (${status})`, "UNKNOWN", status, false);
}

/* ───────────────────────────────────────────
   Configuration
   ─────────────────────────────────────────── */
