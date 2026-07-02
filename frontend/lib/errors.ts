export interface ParsedError {
  message: string;
  code?: string;
  status?: number;
}

const friendlyMessages: Record<string, string> = {
  "already registered": "This email is already registered.",
  "email already registered": "This email is already registered.",
  "already exists": "This record already exists.",
  "invalid email": "Please enter a valid email address.",
  "invalid password": "Incorrect password. Please try again.",
  "invalid credentials": "Incorrect email or password.",
  "not found": "The requested resource was not found.",
  "unauthorized": "Please sign in to continue.",
  "forbidden": "You do not have permission to perform this action.",
  "rate limit": "Too many requests. Please wait a moment and try again.",
  "too many": "Too many attempts. Please wait a few minutes before trying again.",
  "network error": "Unable to reach the server. Check your connection.",
  "failed to fetch": "Unable to reach the server. Check your connection.",
  "timeout": "The request timed out. Please try again.",
  "internal server error": "Something went wrong on our end. Please try again.",
  "validation error": "Please check your input and try again.",
};

function findFriendlyMessage(raw: string): string {
  const lower = raw.toLowerCase();
  for (const [key, msg] of Object.entries(friendlyMessages)) {
    if (lower.includes(key)) return msg;
  }
  return raw;
}

export function parseError(error: unknown): ParsedError {
  if (!error) {
    return { message: "Something went wrong. Please try again." };
  }

  if (error instanceof TypeError) {
    const msg = error.message;
    if (msg.includes("fetch") || msg.includes("network") || msg.includes("NetworkError")) {
      return { message: "Unable to reach the server. Check your connection.", code: "NETWORK_ERROR" };
    }
    return { message: findFriendlyMessage(msg), code: "NETWORK_ERROR" };
  }

  if (error instanceof DOMException) {
    if (error.name === "AbortError") {
      return { message: "Request was cancelled.", code: "ABORTED" };
    }
  }

  if (error instanceof Error) {
    const msg = extractFromString(error.message);
    return { message: msg, status: (error as any).status };
  }

  if (typeof error === "string") {
    return { message: findFriendlyMessage(error) };
  }

  if (typeof error === "object") {
    const obj = error as Record<string, any>;

    if (obj.response?.data?.message) return { message: findFriendlyMessage(obj.response.data.message), status: obj.response.status };
    if (obj.response?.data?.detail) return parseDetail(obj.response.data.detail, obj.response.status);
    if (obj.response?.data?.error) return { message: findFriendlyMessage(obj.response.data.error), status: obj.response.status };
    if (obj.response?.status) return parseDetail(obj.response.statusText, obj.response.status);

    if (obj.data?.message) return { message: findFriendlyMessage(obj.data.message) };
    if (obj.data?.detail) return parseDetail(obj.data.detail);
    if (obj.data?.error) return { message: findFriendlyMessage(obj.data.error) };

    if (obj.message) return { message: extractFromString(obj.message), status: obj.status };
    if (obj.detail) return parseDetail(obj.detail, obj.status);
    if (obj.error) return { message: findFriendlyMessage(String(obj.error)) };

    if (obj.statusText) return { message: findFriendlyMessage(obj.statusText), status: obj.status };

    if (obj.code) return { message: findFriendlyMessage(obj.message || obj.code), code: obj.code };
  }

  return { message: "Something went wrong. Please try again." };
}

async function parseResponseError(res: Response): Promise<ParsedError> {
  try {
    const body = await res.json();
    if (body.detail) return parseDetail(body.detail, res.status);
    if (body.message) return { message: findFriendlyMessage(body.message), status: res.status };
    if (body.error) return { message: findFriendlyMessage(body.error), status: res.status };
  } catch {
    try {
      const text = await res.text();
      if (text) return { message: findFriendlyMessage(text), status: res.status };
    } catch { /* ignore */ }
  }
  return { message: statusText(res.status), status: res.status };
}

function parseDetail(detail: unknown, status?: number): ParsedError {
  if (typeof detail === "string") {
    return { message: findFriendlyMessage(detail), status };
  }
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d: any) => {
        if (typeof d === "string") return d;
        return d.msg || d.message || "";
      })
      .filter(Boolean);
    const joined = msgs.join(". ") || "Validation error. Please check your input.";
    return { message: findFriendlyMessage(joined), status: status || 422 };
  }
  if (typeof detail === "object" && detail !== null) {
    const msg = (detail as any).msg || (detail as any).message || JSON.stringify(detail);
    return { message: findFriendlyMessage(msg), status };
  }
  return { message: "Validation error. Please check your input.", status: 422 };
}

function extractFromString(msg: string): string {
  if (!msg || msg === "[object Object]") {
    return "Something went wrong. Please try again.";
  }
  return findFriendlyMessage(msg);
}

function statusText(code: number): string {
  const map: Record<number, string> = {
    400: "Invalid request. Please check your input.",
    401: "Incorrect email or password.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    409: "This record already exists.",
    422: "Please check your input and try again.",
    429: "Too many requests. Please wait a moment.",
    500: "Something went wrong on our end. Please try again.",
    502: "The server is temporarily unavailable. Please try again.",
    503: "The server is temporarily unavailable. Please try again.",
    504: "The server timed out. Please try again.",
  };
  return map[code] || `An error occurred (${code}). Please try again.`;
}

export function getErrorMessage(error: unknown): string {
  if (typeof error === "string") return findFriendlyMessage(error);
  if (error instanceof Error) {
    const msg = error.message;
    if (!msg || msg === "[object Object]") return "Something went wrong. Please try again.";
    return findFriendlyMessage(msg);
  }
  return parseError(error).message;
}

export function validateEmail(email: string): string | null {
  if (!email || !email.trim()) return "Email is required.";
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.trim())) return "Please enter a valid email address.";
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return "Password is required.";
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (password.length > 128) return "Password must be under 128 characters.";
  return null;
}

export function validateName(name: string): string | null {
  if (!name || !name.trim()) return "Name is required.";
  if (name.trim().length < 1) return "Name must be at least 1 character.";
  if (name.trim().length > 255) return "Name must be under 255 characters.";
  return null;
}
