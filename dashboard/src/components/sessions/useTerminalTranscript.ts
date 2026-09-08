/**
 * Render session transcript from cowrie data, with sanitization and IP redaction.
 */
import type { SessionDetailResponse } from '@/api/generated/types.gen'
import { sanitizeAttackerText } from '@/utils/sanitize'
import { redactIps, type RedactSegment } from '@/utils/redactIps'
import { humanizeDuration } from '@/utils/duration'

const DEFAULT_USER = 'root'
const HOST = 'honeypot'
const MAX_FIELD_BYTES = 8192

// Auth lines: `pre` + password + `post` as flat strings, not RedactSegment[] like commands;
// IPs embedded in the password are still replaced with the literal text `<ip>`.
// Empty password string means no password supplied.
// `time` is captured clock (HH:MM:SS UTC); synthetic banner/close lines use session times.
export type TerminalLine =
  | { id: string; kind: 'banner'; text: string; time?: string }
  | { id: string; kind: 'auth-ok'; pre: string; password: string; post: string; time?: string }
  | { id: string; kind: 'auth-fail'; pre: string; password: string; post: string; time?: string }
  | { id: string; kind: 'command'; user: string; segments: RedactSegment[]; time?: string }
  | { id: string; kind: 'download'; text: string; time?: string }
  | { id: string; kind: 'closed'; text: string; time?: string }

type AuthAttempt = SessionDetailResponse['auth_attempts'][number]
type Command = SessionDetailResponse['commands'][number]
type Download = SessionDetailResponse['downloads'][number]

type Event =
  | { ts: number | null; pri: 0; rowId: number; type: 'auth'; v: AuthAttempt }
  | { ts: number | null; pri: 1; rowId: number; type: 'cmd'; v: Command }
  | { ts: number | null; pri: 2; rowId: number; type: 'dl'; v: Download }

function parseTs(iso: string | null): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? null : t
}

function fmtClock(ts: number | null): string {
  if (ts === null) return ''
  return new Date(ts).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}

function clean(raw: string): string {
  return sanitizeAttackerText(raw, { mode: 'escape', maxBytes: MAX_FIELD_BYTES })
}

function cmp(a: number, b: number): number {
  return a < b ? -1 : a > b ? 1 : 0
}

export function buildTranscript(session: SessionDetailResponse): TerminalLine[] {
  const lines: TerminalLine[] = []

  // The prompt user = first successful login; fall back to the last attempted
  // username, then a generic root. (Many sessions only brute-force credentials
  // and never reach a shell.)
  const firstSuccess = session.auth_attempts.find((a) => a.success)
  const lastAttempt = session.auth_attempts.at(-1)
  const sessionUser = clean(firstSuccess?.username ?? lastAttempt?.username ?? DEFAULT_USER)

  const proto = clean(session.protocol).toUpperCase()
  const where = session.country ? ` from ${clean(session.country)}` : ''
  lines.push({
    id: 'banner',
    kind: 'banner',
    text: `Connecting to ${HOST} over ${proto}${where}...`,
    time: fmtClock(parseTs(session.started_at)),
  })

  // Merge auth + commands + downloads, stable-sorted by timestamp. On an
  // exact tie (cowrie expands a compound one-liner into sub-commands at the
  // same millisecond) order by type then row id, so the compound line and
  // its expansions keep capture order.
  const events: Event[] = []
  for (const a of session.auth_attempts)
    events.push({ ts: parseTs(a.timestamp), pri: 0, rowId: a.id, type: 'auth', v: a })
  for (const c of session.commands)
    events.push({ ts: parseTs(c.timestamp), pri: 1, rowId: c.id, type: 'cmd', v: c })
  for (const d of session.downloads)
    events.push({ ts: parseTs(d.timestamp), pri: 2, rowId: d.id, type: 'dl', v: d })

  events.sort((x, y) => {
    if (x.ts === null && y.ts === null) return cmp(x.pri, y.pri) || cmp(x.rowId, y.rowId)
    if (x.ts === null) return 1
    if (y.ts === null) return -1
    return cmp(x.ts, y.ts) || cmp(x.pri, y.pri) || cmp(x.rowId, y.rowId)
  })

  for (const e of events) {
    const time = fmtClock(e.ts)
    if (e.type === 'auth') {
      // Credentials are attacker-supplied, exactly like a command, so they go
      // through the same blotting. Without this an IP typed into a username or
      // password rendered verbatim here while SessionExpansion's own facts
      // panel redacted the identical field.
      const user = redactIps(clean(e.v.username), undefined, { numericHosts: false }).text
      const password = redactIps(clean(e.v.password), undefined, {
        numericHosts: false,
      }).text
      if (e.v.success) {
        lines.push({
          id: `auth-${e.v.id}`,
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password,
          post: ` for ${user}.`,
          time,
        })
      } else {
        lines.push({
          id: `auth-${e.v.id}`,
          kind: 'auth-fail',
          pre: `${user}@${HOST}'s password: `,
          password,
          post: ' - Permission denied (password).',
          time,
        })
      }
    } else if (e.type === 'cmd') {
      const { segments } = redactIps(clean(e.v.input))
      lines.push({ id: `cmd-${e.v.id}`, kind: 'command', user: sessionUser, segments, time })
    } else {
      const urlText = e.v.url ? redactIps(clean(e.v.url)).text : '(no link - sent directly)'
      const sha = e.v.sha256 ? ` - sha256 ${e.v.sha256.slice(0, 12)}...` : ''
      lines.push({
        id: `dl-${e.v.id}`,
        kind: 'download',
        text: `downloaded file: ${urlText}${sha}`,
        time,
      })
    }
  }

  const dur = humanizeDuration(session.started_at, session.ended_at)
  lines.push({
    id: 'closed',
    kind: 'closed',
    text:
      dur === '-'
        ? `Connection to ${HOST} closed.`
        : `Connection to ${HOST} closed. Session lasted ${dur}.`,
    time: fmtClock(parseTs(session.ended_at)),
  })

  return lines
}
