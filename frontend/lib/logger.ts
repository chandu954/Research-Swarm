/**
 * Structured, dependency-free frontend logger.
 *
 * Every entry is emitted as a single JSON-friendly object so browser consoles,
 * error reporting tools, and future transports can consume the same shape.
 * Debug entries are suppressed in production builds; warn/error always emit.
 */

export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogContext {
  [key: string]: unknown;
}

export interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  scope?: string;
  context?: LogContext;
}

type Sink = (entry: LogEntry) => void;

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

const isProduction = process.env.NODE_ENV === "production";
const minimumLevel: LogLevel = isProduction ? "info" : "debug";

function serializeError(error: unknown): unknown {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: isProduction ? undefined : error.stack,
    };
  }
  return error;
}

function normalizeContext(context?: LogContext): LogContext | undefined {
  if (!context) return undefined;
  const normalized: LogContext = {};
  for (const [key, value] of Object.entries(context)) {
    normalized[key] = value instanceof Error ? serializeError(value) : value;
  }
  return normalized;
}

const consoleSink: Sink = (entry) => {
  const method =
    entry.level === "error"
      ? console.error
      : entry.level === "warn"
        ? console.warn
        : entry.level === "info"
          ? console.info
          : console.debug;
  method(`[${entry.level}] ${entry.message}`, entry);
};

let sink: Sink = consoleSink;

/** Replace the transport (e.g. to forward entries to an observability backend). */
export function setLogSink(next: Sink | null): void {
  sink = next ?? consoleSink;
}

export function isLevelEnabled(level: LogLevel): boolean {
  return LEVEL_ORDER[level] >= LEVEL_ORDER[minimumLevel];
}

export function createLogger(scope?: string) {
  const emit = (level: LogLevel, message: string, context?: LogContext) => {
    if (!isLevelEnabled(level)) return;
    sink({
      level,
      message,
      timestamp: new Date().toISOString(),
      scope,
      context: normalizeContext(context),
    });
  };

  return {
    debug: (message: string, context?: LogContext) => emit("debug", message, context),
    info: (message: string, context?: LogContext) => emit("info", message, context),
    warn: (message: string, context?: LogContext) => emit("warn", message, context),
    error: (message: string, context?: LogContext) => emit("error", message, context),
    child: (childScope: string) => createLogger(scope ? `${scope}:${childScope}` : childScope),
  };
}

export const logger = createLogger("frontend");
