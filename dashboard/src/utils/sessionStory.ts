import type { SessionSummaryResponse } from '@/api/generated/types.gen'

export interface StoryBadge {
  label: string
  tone: 'amber' | 'ok' | 'bad' | 'dim'
  title: string
  /** Key into ICONS; the count carries the meaning, the icon carries the kind. */
  icon?: 'terminal' | 'file' | 'relay'
  /** Stands in for the word on phones, where the chip shrinks to a bare icon. */
  glyph?: 'key' | 'login' | 'terminal' | 'eye'
}

const plural = (n: number, w: string): string => (n === 1 ? w : `${w}s`)

export function buildStory(row: {
  n_commands: number
  n_downloads: number
  n_tcpip: number
  auth_success: boolean
  category?: SessionSummaryResponse['category']
}): StoryBadge[] {
  const badges: StoryBadge[] = []
  if (row.n_commands > 0)
    badges.push({
      label: String(row.n_commands),
      icon: 'terminal',
      tone: 'amber',
      title: `${row.n_commands} ${plural(row.n_commands, 'command')} typed`,
    })
  if (row.n_downloads > 0)
    badges.push({
      label: String(row.n_downloads),
      icon: 'file',
      tone: 'amber',
      title: `${row.n_downloads} ${plural(row.n_downloads, 'file')} downloaded`,
    })
  if (row.n_tcpip > 0)
    badges.push({
      label: String(row.n_tcpip),
      icon: 'relay',
      tone: 'amber',
      title: `${row.n_tcpip} ${plural(row.n_tcpip, 'attempt')} to reach other computers through the honeypot`,
    })
  // Anything above already implies control, so the outcome badge only earns a
  // slot when the session did nothing else worth showing.
  if (badges.length === 0) {
    // A probe or failed login never got a prompt, so it must not read as a login.
    if (row.category === 'probe' || row.category === 'failed') {
      badges.push(outcomeBadge(row.category))
      return badges
    }
    badges.push(
      row.auth_success
        ? {
            label: 'control',
            glyph: 'key',
            tone: 'ok',
            title: 'Got a command prompt but ran nothing',
          }
        : {
            label: 'login only',
            glyph: 'login',
            tone: 'bad',
            title: 'Logged in but never got a command prompt',
          },
    )
  }
  return badges
}

/** The session's outcome in words, for phones where the story chips are bare icons. */
export const OUTCOME_TEXT: Record<SessionSummaryResponse['category'], string> = {
  active: 'Got control and ran commands',
  login: 'Got control, ran nothing',
  failed: 'Tried to log in, never got in',
  probe: 'Connected, never tried to log in',
}

/** The outcome as the same bare icon the rows use, for the phone panel's facts. */
export function outcomeBadge(category: SessionSummaryResponse['category']): StoryBadge {
  const kind: Record<typeof category, Pick<StoryBadge, 'label' | 'glyph' | 'tone'>> = {
    active: { label: 'commands', glyph: 'terminal', tone: 'amber' },
    login: { label: 'control', glyph: 'key', tone: 'ok' },
    failed: { label: 'failed', glyph: 'login', tone: 'bad' },
    probe: { label: 'probe', glyph: 'eye', tone: 'dim' },
  }
  return { ...kind[category], title: OUTCOME_TEXT[category] }
}

// Shared by the hex tooltip and the Session column header, so keyboard users (the hex is not a
// Tab stop) get the same explanation.
export const SCORE_TIP =
  'Interest score - higher when a session ran commands, dropped files, got control or tried to relay'

/**
 * Normalize interest score against dataset ceiling so full color saturation aligns with actual data, not a guessed constant.
 */
export function scoreFrac(interest: number, ceiling: number): number {
  return Math.min(1, Math.max(0, interest) / Math.max(1, ceiling))
}

export type SessionRow = SessionSummaryResponse
