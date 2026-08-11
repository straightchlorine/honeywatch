/**
 * Retry transient failures (network errors, 5xx) capped at 2; never 4xx.
 * Note: generated client puts HTTP status in `code` property, not `status`.
 */
export function shouldRetry(failureCount: number, err: unknown): boolean {
  const code = (err as { code?: number } | null)?.code
  return failureCount < 2 && (code === undefined || code >= 500)
}
