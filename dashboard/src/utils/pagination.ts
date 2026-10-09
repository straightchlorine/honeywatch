import type { ListSessionsData } from '@/api/generated/types.gen'

// Shared by SessionsView and SessionDetailView: the detail page rebuilds the list's query
// key to read its cached page, so the two must agree or the cache lookup misses.
export const SESSIONS_PER_PAGE = 40

const MIN_QUERY_LEN = 2
const SHA256_RE = /^[0-9a-f]{64}$/

type ListQuery = NonNullable<ListSessionsData['query']>

// List URL params -> list request params. `get` returns the raw value for a key, so this
// works for both route.query and URLSearchParams; non-strings (repeated keys) count as absent.
// A malformed ?sha256= is dropped here because the API 422s on it.
export function sessionsListQuery(get: (key: string) => unknown): ListQuery {
  const str = (k: string): string => {
    const v = get(k)
    return typeof v === 'string' ? v : ''
  }
  const term = str('q')
  const sha = str('sha256')
  return {
    page: Math.max(1, parseInt(str('page'), 10) || 1),
    per_page: SESSIONS_PER_PAGE,
    sort: (str('sort') as ListQuery['sort']) || 'interest',
    order: (str('order') as ListQuery['order']) || undefined,
    has: str('has') || undefined,
    country: str('country') || undefined,
    q: term.length >= MIN_QUERY_LEN ? term : undefined,
    sha256: SHA256_RE.test(sha) ? sha : undefined,
  }
}
