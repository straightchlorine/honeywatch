import type { SessionSummaryResponse } from '@/api/generated/types.gen'

export interface StoryBadge {
  label: string
  tone: 'amber' | 'ok' | 'bad'
  title: string
}

const plural = (n: number, w: string): string => (n === 1 ? w : `${w}s`)

export function buildStory(row: {
  n_commands: number
  n_downloads: number
  n_tcpip: number
  auth_success: boolean
}): StoryBadge[] {
  const badges: StoryBadge[] = []
  if (row.n_commands > 0) badges.push({ label: `${row.n_commands} ${plural(row.n_commands, 'cmd')}`, tone: 'amber', title: `${row.n_commands} ${plural(row.n_commands, 'command')} typed` })
  if (row.n_downloads > 0) badges.push({ label: `${row.n_downloads} ${plural(row.n_downloads, 'file')}`, tone: 'amber', title: `${row.n_downloads} ${plural(row.n_downloads, 'file')} downloaded` })
  if (row.n_tcpip > 0) badges.push({ label: `${row.n_tcpip} ${plural(row.n_tcpip, 'relay')}`, tone: 'amber', title: `${row.n_tcpip} ${plural(row.n_tcpip, 'attempt')} to reach other computers through the honeypot` })
  badges.push(
    row.auth_success ? { label: 'control', tone: 'ok', title: 'Got a command prompt - full control of the honeypot' } : { label: 'login only', tone: 'bad', title: 'Logged in but never got a command prompt' },
  )
  return badges
}

/**
 * Normalize interest score against dataset ceiling so full color saturation aligns with actual data, not a guessed constant.
 */
export function scoreFrac(interest: number, ceiling: number): number {
  return Math.min(1, Math.max(0, interest) / Math.max(1, ceiling))
}

export type SessionRow = SessionSummaryResponse
