import type { ListSessionsData } from '@/api/generated/types.gen'

// Shared by SessionsView and SessionDetailView: the detail page rebuilds the list's query
// key to read its cached page, so the two must agree or the cache lookup misses.
export const SESSIONS_PER_PAGE = 40

const MIN_QUERY_LEN = 2
const SHA256_RE = /^[0-9a-f]{64}$/
// Mirror the API's limits (api/src/schemas/sessions.py) so a bad URL param never 422s.
const MAX_PAGE = 50_000
const SORTS: readonly string[] = ['recent', 'country', 'active', 'interest', 'duration']
const HAS_TOKENS: readonly string[] = ['commands', 'downloads', 'success', 'tcpip', 'none']

type ListQuery = NonNullable<ListSessionsData['query']>

// Same rules as the API's _validate_has: every token known, and 'none' only on its own.
const validHas = (v: string): boolean => {
  const tokens = v.split(',')
  if (!tokens.every((t) => HAS_TOKENS.includes(t))) return false
  return !tokens.includes('none') || tokens.length === 1
}

// List URL params -> list request params. `get` returns the raw value for a key, so this
// works for both route.query and URLSearchParams; non-strings (repeated keys) count as absent.
// Malformed ?page=, ?sort=, ?has= and ?sha256= are clamped or dropped here because the API
// 422s on them.
export function sessionsListQuery(get: (key: string) => unknown): ListQuery {
  const str = (k: string): string => {
    const v = get(k)
    return typeof v === 'string' ? v : ''
  }
  const term = str('q')
  const sha = str('sha256')
  const sort = str('sort')
  const has = str('has')
  return {
    page: Math.min(MAX_PAGE, Math.max(1, parseInt(str('page'), 10) || 1)),
    per_page: SESSIONS_PER_PAGE,
    fold: true,
    sort: (SORTS.includes(sort) ? sort : 'interest') as ListQuery['sort'],
    order: (str('order') as ListQuery['order']) || undefined,
    has: validHas(has) ? has : undefined,
    country: str('country') || undefined,
    q: term.length >= MIN_QUERY_LEN ? term : undefined,
    sha256: SHA256_RE.test(sha) ? sha : undefined,
  }
}
