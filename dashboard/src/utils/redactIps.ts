/**
 * Mask IPv4/IPv6 literals in attacker-controlled text before rendering, returning
 * segments for styled redaction.
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

export const IP_BLOT = '<ip>'

const IPV4 = String.raw`(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)`

// IPv6 canonical matcher: requires either 8 groups or `::` run, so time strings like
// "13:41:49" never match. First three branches consume IPv4-in-IPv6 forms so the
// embedded dotted-quad is fully blotted, not left in cleartext.
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

// Standalone dotted-quad IPv4: lookback/lookahead block 5th octet to avoid
// partially blotting version strings like `lib.so.1.2.3.4.5`. Use `not alnum`
// not `\b`: underscore is a word char, so `\b` fails on `MGLNDD_204.168.164.170_22`.
// Corresponds to _IPV4_STANDALONE in redact.py.
const IPV4_STANDALONE = String.raw`(?<!\d\.)(?<![0-9A-Za-z])${IPV4}(?![0-9A-Za-z])(?!\.\d)`

// Alternate-encoding hosts (decimal, hex, octal) resolve to IPs but slip past
// dotted-quad; anchored on URI schemes (ftp://, tftp://, scp://, not just http(s)).
const NUMERIC_HOST = String.raw`(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})(?:\.(?:0[xX][0-9A-Fa-f]+|0[0-7]+|\d{1,10})){0,3}`
// `(?!:[0-9A-Fa-f]*:)` stops the host rule from swallowing the leading group of an
// (unbracketed) IPv6 literal like `2001:db8::1.2.3.4`, which the IPv6 rule then
// matches in full instead of leaving a `db8` fragment behind.
const URL_NUMERIC_HOST = String.raw`(?<scheme>\b[A-Za-z][A-Za-z0-9+.\-]*:\/\/(?:[^/?#\s@]+@)?)(?<host>${NUMERIC_HOST})(?!:[0-9A-Fa-f]*:)(?=[/:?#\s]|$)`

// Shell commands drop the scheme; catch bare integer-encoded IPs with length
// bounds (hex 5-8 digits, octal 8-11, decimal 8-10) to avoid ports, chmod flags,
// timeouts, and timestamps, then range-check before blotting.
const SCHEMELESS_NUMERIC_HOST = String.raw`(?<![\w.:-])(?<numtok>0[xX][0-9A-Fa-f]{5,8}|0[0-7]{8,11}|\d{8,10})(?![\w.:-])`

// Excludes 0.x.x.x (non-routable).
const MIN_IP_INT = 16777216
const MAX_IP_INT = 4294967295

function parseNumericToken(tok: string): number {
  if (tok.slice(0, 2) === '0x' || tok.slice(0, 2) === '0X') return parseInt(tok, 16)
  if (tok[0] === '0' && tok.length > 1 && /^[0-7]+$/.test(tok.slice(1))) {
    return parseInt(tok, 8)
  }
  return parseInt(tok, 10)
}

// Recognize pre-blotted tokens from server-side redaction (authoritative gate);
// render as styled blots and catch any missed IPs (defense-in-depth).
const BLOT_RE = IP_BLOT.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Order matters: blot token and IPv6 first to consume full literals (else
// numeric-host grabs leading `::` groups and leaves hex fragments); then
// dotted-quad IPv4; URL numeric-host; schemeless last (most conservative).
const LITERAL_ALTS = `(?:${BLOT_RE})|(?:${IPV6})|(?:${IPV4_STANDALONE})|(?:${URL_NUMERIC_HOST})`
const IP_SOURCE = `${LITERAL_ALTS}|(?:${SCHEMELESS_NUMERIC_HOST})`

export interface RedactOptions {
  /**
   * Also blot a bare 8-10 digit / hex / octal integer that decodes to a
   * routable IPv4. True for shell commands and URLs, where a bare integer
   * really is a host. Pass false for credentials, SSH banners and filenames:
   * "123456789" is one of the most sprayed passwords there is, and blotting it
   * corrupts the credential views. Corresponds to `numeric_hosts` in redact.py.
   */
  numericHosts?: boolean
}

export function redactIps(
  text: string,
  token: string = IP_BLOT,
  { numericHosts = true }: RedactOptions = {},
): RedactResult {
  const segments: RedactSegment[] = []
  const re = new RegExp(numericHosts ? IP_SOURCE : LITERAL_ALTS, 'g')
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
    const numtok = m.groups?.numtok
    if (numtok !== undefined) {
      // Schemeless numeric-host: only blot if it actually decodes into a
      // plausible IPv4 address, otherwise leave the token alone and move on.
      const value = parseNumericToken(numtok)
      if (value < MIN_IP_INT || value > MAX_IP_INT) {
        re.lastIndex = m.index + m[0].length
        continue
      }
      if (m.index > last) segments.push({ text: text.slice(last, m.index), redacted: false })
      segments.push({ text: token, redacted: true })
      count++
      last = m.index + m[0].length
    } else if (scheme !== undefined && host !== undefined) {
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
