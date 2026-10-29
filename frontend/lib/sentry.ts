/**
 * Optional Sentry error tracking for the frontend.
 *
 * Initializes Sentry only when NEXT_PUBLIC_SENTRY_DSN is set, falling back
 * silently otherwise. Import and call initSentry() from your app root layout.
 */

export function initSentry(): void {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  try {
    void import("@sentry/nextjs").then(({ init }) => {
      init({
        dsn,
        environment:
          process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "production",
        tracesSampleRate: Number(
          process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
        ),
        enabled: process.env.NODE_ENV === "production",
      });
    });
  } catch {
    // Sentry not installed — fail silently.
  }
}

export function captureException(
  error: unknown,
  context?: Record<string, unknown>,
): void {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  try {
    void import("@sentry/nextjs").then(({ captureException: capture }) => {
      capture(error as Error, { contexts: { frontend: context } });
    });
  } catch {
    // Fail silently if Sentry isn't available.
  }
}
