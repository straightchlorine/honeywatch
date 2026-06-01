import type { SessionSummaryResponse } from '@/api/generated/types.gen'

export type SessionClassKind = SessionSummaryResponse['category']

export interface SessionClass {
  kind: SessionClassKind
  label: string
  title: string
  /** Non-color cue so badge severity survives grayscale / color blindness. */
  glyph: string
}

/**
 * Presentation metadata for each server-assigned session category. The
 * classification itself is owned by the API (`category` field, computed once in
 * `services/categories.classify_category`); the dashboard only maps it to a
 * label, tooltip and a non-color glyph. The priority logic no longer lives here.
 */
const CLASS_META: Record<
  SessionClassKind,
  Omit<SessionClass, 'kind' | 'title'> & { title: string }
> = {
  // Label avoids "active" -- these sessions are over, not ongoing.
  active: { label: 'CLI', title: 'Ran shell commands', glyph: '>' },
  login: { label: 'Login', title: 'Logged in, no commands run', glyph: '✓' },
  failed: { label: 'Failed auth', title: 'Login attempts, none succeeded', glyph: '✕' },
  probe: { label: 'Probe', title: 'Connection only, no login attempts', glyph: '·' },
}

/**
 * Turn a server-classified session into badge presentation. Reads `s.category`
 * (no re-derivation) and enriches the "active" tooltip with the command count.
 */
export function sessionClass(
  s: Pick<SessionSummaryResponse, 'category' | 'command_count'>,
): SessionClass {
  const kind = s.category
  const meta = CLASS_META[kind]
  const title =
    kind === 'active'
      ? `${s.command_count} command${s.command_count === 1 ? '' : 's'} run`
      : meta.title
  return { kind, label: meta.label, title, glyph: meta.glyph }
}
