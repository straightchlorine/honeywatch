/**
 * Resilient loader for code-split chunks (lazy components + lazy routes).
 *
 * Two distinct failure modes are handled:
 *   - Transient blip (network hiccup, a momentary edge 429): a short retry with
 *     exponential backoff + jitter usually rides it out.
 *   - Stale deploy: after a new build, the already-loaded index.html points at
 *     hashed chunk filenames that no longer exist (404). Retrying the dead URL
 *     can never succeed, so the only recovery is a full reload that fetches the
 *     fresh index.html. That reload is guarded against loops -- at most one
 *     within RELOAD_WINDOW_MS; after that the error is surfaced (to the nearest
 *     ErrorBoundary for components, or router.onError for routes).
 *
 * Shared by lazyComponent() and the router's lazy route imports so both
 * surfaces recover identically and a single reload guard governs them.
 */

const RELOAD_GUARD_KEY = 'honeywatch:chunk-reload-at'
const RELOAD_WINDOW_MS = 10_000
const DEFAULT_RETRIES = 2
const BASE_DELAY_MS = 300

/** Backoff for retry `n` (0-based): BASE * 2^n, plus up to 1x jitter. */
function jitteredBackoff(n: number): number {
  const base = BASE_DELAY_MS * 2 ** n
  return base + Math.random() * base
}

/** Heuristic for "the chunk failed to load" (vs a runtime error inside it). */
export function isChunkLoadError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err)
  return /dynamically imported module|importing a module script failed|failed to fetch|error loading/i.test(
    msg,
  )
}

/**
 * One-shot full reload to recover from a stale-deploy chunk 404. Guarded so a
 * genuinely broken deploy cannot loop. Returns true if a reload was triggered.
 */
export function attemptStaleChunkReload(): boolean {
  try {
    const last = Number(sessionStorage.getItem(RELOAD_GUARD_KEY) ?? 0)
    if (Date.now() - last < RELOAD_WINDOW_MS) return false
    sessionStorage.setItem(RELOAD_GUARD_KEY, String(Date.now()))
  } catch {
    // sessionStorage unavailable (private mode etc.) -> don't reload, surface the error.
    return false
  }
  window.location.reload()
  return true
}

export function retryImport<T>(loader: () => Promise<T>, retries = DEFAULT_RETRIES): Promise<T> {
  const attempt = (n: number): Promise<T> =>
    loader().catch((err: unknown) => {
      if (n < retries) {
        const wait = jitteredBackoff(n)
        return new Promise<void>((resolve) => setTimeout(resolve, wait)).then(() => attempt(n + 1))
      }
      // Retries exhausted -- most likely a stale deploy. Reload to the fresh
      // index.html; if we already reloaded recently, give up and surface.
      if (attemptStaleChunkReload()) {
        // Hold the loading state until the page navigates away.
        return new Promise<T>(() => {})
      }
      throw err
    })
  return attempt(0)
}
