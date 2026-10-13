import type { OutcomeCountsResponse } from '@/api/generated/types.gen'

export interface OutcomeRow {
  /** has= token this row toggles. */
  token: string
  label: string
  /** Field on OutcomeCountsResponse this row's count comes from - differs
   * from `token` for "Got control": the query token is `success`
   * (auth_success), the count field is `shell` (accepted login). */
  countKey: keyof OutcomeCountsResponse
}

export const MAIN_ROWS: OutcomeRow[] = [
  { token: 'success', label: 'Got control', countKey: 'shell' },
  { token: 'commands', label: 'Ran commands', countKey: 'commands' },
  { token: 'tcpip', label: 'Tried to relay', countKey: 'tcpip' },
  { token: 'downloads', label: 'Dropped a file', countKey: 'downloads' },
]
// Complement of the four above (interest == 0), not a fifth member of the
// same set - kept out of MAIN_ROWS and given its own divider in the panel.
export const NONE_ROW: OutcomeRow = { token: 'none', label: 'Nothing at all', countKey: 'none' }
export const ALL_ROWS = [...MAIN_ROWS, NONE_ROW]

/** Toggles one token in a has= value; 'none' is mutually exclusive (server 422s on mixed has=none). */
export function toggleHas(current: string, token: string): string {
  // Unknown tokens are a no-op, so they cannot clear a 'none' selection.
  if (!ALL_ROWS.some((r) => r.token === token)) return current
  const next = new Set(current ? current.split(',').map((t) => t.trim()) : [])
  if (token === 'none') {
    if (next.has('none')) next.delete('none')
    else {
      next.clear()
      next.add('none')
    }
  } else if (next.has(token)) next.delete(token)
  else {
    next.delete('none')
    next.add(token)
  }
  // Canonical row order, not insertion order, so the emitted string is
  // deterministic regardless of click order.
  return ALL_ROWS.filter((r) => next.has(r.token))
    .map((r) => r.token)
    .join(',')
}
