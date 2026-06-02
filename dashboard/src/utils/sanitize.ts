/**
 * Single source of truth for neutralizing attacker-controlled text before it is
 * rendered in the dashboard. Cowrie captures (usernames, passwords, command
 * input, download URLs) and server error messages can contain terminal control
 * sequences and Unicode bidi overrides that spoof how text renders. We either
 * strip or hex-escape those code points; ordinary whitespace can be preserved
 * for multi-line content (e.g. pretty-printed JSON).
 *
 * Used by both the session payload viewer (escape mode) and the error boundary
 * (strip mode) so the rule cannot drift between call sites.
 */

export type SanitizeMode = 'escape' | 'strip'

export interface SanitizeOptions {
  /** 'escape' renders dangerous code points as \xHH; 'strip' removes them. */
  mode?: SanitizeMode
  /** Keep TAB/LF/CR (default true). Set false for single-line messages. */
  allowWhitespace?: boolean
  /** Optional UTF-8 byte cap, applied to the RAW input BEFORE the scan so a
   *  pathological payload never gets fully scanned. Appends a truncation marker. */
  maxBytes?: number
}

const TRUNCATION_MARKER = '\n... [truncated]'

/** True for C0 controls (minus allowed whitespace), DEL/C1, bidi marks + overrides. */
function isDangerous(code: number, allowWhitespace: boolean): boolean {
  const isAllowedWs = allowWhitespace && (code === 0x09 || code === 0x0a || code === 0x0d)
  if (isAllowedWs) return false
  return (
    code <= 0x1f || // C0 controls
    (code >= 0x7f && code <= 0x9f) || // DEL + C1 controls
    code === 0x200e || // LRM
    code === 0x200f || // RLM
    (code >= 0x202a && code <= 0x202e) || // bidi embeddings/overrides
    (code >= 0x2066 && code <= 0x2069) // bidi isolates
  )
}

/** Truncate to at most `maxBytes` UTF-8 bytes without splitting a code point. */
function truncateToBytes(raw: string, maxBytes: number): { text: string; truncated: boolean } {
  const encoded = new TextEncoder().encode(raw)
  if (encoded.length <= maxBytes) return { text: raw, truncated: false }
  // Decoding a byte slice with a non-fatal decoder drops any trailing partial
  // multi-byte sequence, so we never emit a broken code point.
  const text = new TextDecoder('utf-8', { fatal: false }).decode(encoded.slice(0, maxBytes))
  return { text, truncated: true }
}

export function sanitizeAttackerText(raw: string, opts: SanitizeOptions = {}): string {
  const { mode = 'escape', allowWhitespace = true, maxBytes } = opts

  let text = raw
  let truncated = false
  if (maxBytes !== undefined) {
    const t = truncateToBytes(raw, maxBytes)
    text = t.text
    truncated = t.truncated
  }

  let out = ''
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i)
    if (isDangerous(code, allowWhitespace)) {
      if (mode === 'escape') {
        out += '\\x' + code.toString(16).toUpperCase().padStart(2, '0')
      }
      // strip mode: drop the character
    } else {
      out += text[i]
    }
  }

  return truncated ? out + TRUNCATION_MARKER : out
}
