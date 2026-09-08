import type { SessionSummaryResponse } from '@/api/generated/types.gen'

export interface StoryBadge {
  label: string
  tone: 'amber' | 'ok' | 'bad'
  title: string
  /** Key into ICONS; the count carries the meaning, the icon carries the kind. */
  icon?: 'terminal' | 'file' | 'relay'
}

const plural = (n: number, w: string): string => (n === 1 ? w : `${w}s`)

export function buildStory(row: {
  n_commands: number
  n_downloads: number
  n_tcpip: number
  auth_success: boolean
}): StoryBadge[] {
  const badges: StoryBadge[] = []
  if (row.n_commands > 0) badges.push({ label: String(row.n_commands), icon: 'terminal', tone: 'amber', title: `${row.n_commands} ${plural(row.n_commands, 'command')} typed` })
  if (row.n_downloads > 0) badges.push({ label: String(row.n_downloads), icon: 'file', tone: 'amber', title: `${row.n_downloads} ${plural(row.n_downloads, 'file')} downloaded` })
  if (row.n_tcpip > 0) badges.push({ label: String(row.n_tcpip), icon: 'relay', tone: 'amber', title: `${row.n_tcpip} ${plural(row.n_tcpip, 'attempt')} to reach other computers through the honeypot` })
  // Anything above already implies control, so the outcome badge only earns a
  // slot when the session did nothing else worth showing.
  if (badges.length === 0) {
    badges.push(
      row.auth_success
        ? { label: 'control', tone: 'ok', title: 'Got a command prompt but ran nothing' }
        : { label: 'login only', tone: 'bad', title: 'Logged in but never got a command prompt' },
    )
  }
  return badges
}

/**
 * Normalize interest score against dataset ceiling so full color saturation aligns with actual data, not a guessed constant.
 */
export function scoreFrac(interest: number, ceiling: number): number {
  return Math.min(1, Math.max(0, interest) / Math.max(1, ceiling))
}

export type SessionRow = SessionSummaryResponse
