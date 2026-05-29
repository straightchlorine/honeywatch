/**
 * TanStack Query retry predicate. The generated client throws the API error
 * envelope ({ code: number, status: string, message }) on a non-2xx response,
 * so the HTTP status lives in `code` (NOT `status`, which is the reason phrase).
 * Network failures throw a plain Error with no `code`.
 *
 * Retry transient failures only: network errors (no code) and 5xx, capped at 2.
 * 4xx are deterministic client errors and are never retried.
 */
export function shouldRetry(failureCount: number, err: unknown): boolean {
  const code = (err as { code?: number } | null)?.code
  return failureCount < 2 && (code === undefined || code >= 500)
}
