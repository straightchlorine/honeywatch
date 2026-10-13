/**
 * Query hooks with defaults (refetchInterval, retry, staleTime). Override in views as needed.
 */
import './client'

export * from './generated/@tanstack/vue-query.gen'

interface SuspendableQuery {
  suspense: () => Promise<unknown>
  error: { value: unknown }
  data: { value: unknown }
}

/** suspense() resolves on a failed fetch; throw the API error so views never read undefined data. */
export async function suspenseAll(...queries: SuspendableQuery[]): Promise<void> {
  await Promise.all(queries.map((q) => q.suspense()))
  for (const q of queries) {
    if (q.error.value && q.data.value === undefined) throw q.error.value
  }
}
