/**
 * Turn a captured session into an ordered list of terminal lines for the replay.
 *
 * Honesty contract: we render ONLY what cowrie captured -- attacker-typed input,
 * login outcomes, and download events. Cowrie stores no command stdout, so the
 * transcript never fabricates output. Annotations (banner / login / download /
 * close) are tagged with their own line kinds so the renderer can mark them as
 * NOT attacker output. Every attacker string is run through `sanitizeAttackerText`
 * and command/URL text through `redactIps` (always blot).
 */
import type { SessionDetailResponse } from '@/api/generated/types.gen'
import { sanitizeAttackerText } from '@/utils/sanitize'
import { redactIps, type RedactSegment } from '@/utils/redactIps'
import { humanizeDuration } from '@/utils/duration'

const DEFAULT_USER = 'root'
const HOST = 'honeypot'
const MAX_FIELD_BYTES = 8192

// Auth lines surface the captured credential: `pre` + the attacker's password
// (rendered as a highlighted chip by the view) + `post`. Passwords are the
// honeypot's core public data (cf. the Overview top-passwords board), so unlike
// IPs they are shown verbatim, only sanitized. `password === ''` => no password
// supplied; the view shows an explicit empty marker.
// `time` is the captured event clock (HH:MM:SS UTC), rendered in a left gutter
// so the replay reads like a real terminal log. Synthetic banner/close lines
// borrow the session start/end time; lines with no timestamp leave it blank.
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

// HH:MM:SS in UTC (the capture clock). Empty when there is no timestamp.
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

  // 1. synthetic connect banner (borrows the session start time)
  const proto = clean(session.protocol).toUpperCase()
  const where = session.country ? ` from ${clean(session.country)}` : ''
  lines.push({
    id: 'banner',
    kind: 'banner',
    text: `Connecting to ${HOST} over ${proto}${where}…`,
    time: fmtClock(parseTs(session.started_at)),
  })

  // 2. merge auth + commands + downloads, stable-sorted by timestamp. On an
  //    exact tie (cowrie expands a compound one-liner into sub-commands at the
  //    same millisecond) order by type then row id, so the compound line and
  //    its expansions keep capture order.
  const events: Event[] = []
  for (const a of session.auth_attempts)
    events.push({ ts: parseTs(a.timestamp), pri: 0, rowId: a.id, type: 'auth', v: a })
  for (const c of session.commands)
    events.push({ ts: parseTs(c.timestamp), pri: 1, rowId: c.id, type: 'cmd', v: c })
  for (const d of session.downloads)
    events.push({ ts: parseTs(d.timestamp), pri: 2, rowId: d.id, type: 'dl', v: d })

  events.sort((x, y) => {
    if (x.ts === null && y.ts === null) return cmp(x.pri, y.pri) || cmp(x.rowId, y.rowId)
    if (x.ts === null) return 1 // nulls last
    if (y.ts === null) return -1
    return cmp(x.ts, y.ts) || cmp(x.pri, y.pri) || cmp(x.rowId, y.rowId)
  })

  // 3. emit one line per event
  for (const e of events) {
    const time = fmtClock(e.ts)
    if (e.type === 'auth') {
      const user = clean(e.v.username)
      const password = clean(e.v.password)
      if (e.v.success) {
        // "Accepted password ‹pw› for root."
        lines.push({
          id: `auth-${e.v.id}`,
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password,
          post: ` for ${user}.`,
          time,
        })
      } else {
        // "root@honeypot's password: ‹pw› — Permission denied (password)." The
        // password sits exactly where the attacker typed it before the denial.
        lines.push({
          id: `auth-${e.v.id}`,
          kind: 'auth-fail',
          pre: `${user}@${HOST}'s password: `,
          password,
          post: ' — Permission denied (password).',
          time,
        })
      }
    } else if (e.type === 'cmd') {
      const { segments } = redactIps(clean(e.v.input))
      lines.push({ id: `cmd-${e.v.id}`, kind: 'command', user: sessionUser, segments, time })
    } else {
      const urlText = e.v.url ? redactIps(clean(e.v.url)).text : '(in-band capture)'
      const sha = e.v.sha256 ? ` · sha256 ${e.v.sha256.slice(0, 12)}…` : ''
      lines.push({
        id: `dl-${e.v.id}`,
        kind: 'download',
        text: `downloaded payload: ${urlText}${sha}`,
        time,
      })
    }
  }

  // 4. closing line (borrows the session end time)
  const dur = humanizeDuration(session.started_at, session.ended_at)
  lines.push({
    id: 'closed',
    kind: 'closed',
    text:
      dur === '—'
        ? `Connection to ${HOST} closed.`
        : `Connection to ${HOST} closed. Session lasted ${dur}.`,
    time: fmtClock(parseTs(session.ended_at)),
  })

  return lines
}
