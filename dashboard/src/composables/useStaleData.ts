/**
 * Is anything on screen showing cached data because a refetch is failing?
 */
import { onScopeDispose, ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'

export function useStaleData() {
  const client = useQueryClient()
  const stale = ref(false)

  function recompute(): void {
    // Check for errors, not fetching status; fetches in flight are normal
    const failing = client
      .getQueryCache()
      .getAll()
      .some((q) => q.state.status === 'error' || q.state.fetchFailureCount > 0)
    stale.value = failing
  }

  recompute()
  // Returns its own unsubscribe; the scope disposes it, so a view that
  // unmounts mid-outage leaves no listener behind.
  onScopeDispose(client.getQueryCache().subscribe(recompute))

  return { stale }
}
