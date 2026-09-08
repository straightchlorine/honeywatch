/**
 * Retry transient failures (network errors, 5xx) capped at 2; never 4xx (generated client puts status in `code` property).
 */
export function shouldRetry(failureCount: number, err: unknown): boolean {
  const code = (err as { code?: number } | null)?.code
  return failureCount < 2 && (code === undefined || code >= 500)
}
