import type {
  CharsetClassResponse,
  CredentialLengthResponse,
  TopCredentialResponse,
  TopPasswordResponse,
} from '@/api/generated/types.gen'
import { sanitizeAttackerText } from '@/utils/sanitize'
import { redactIps } from '@/utils/redactIps'
import { fmtNumber } from './format'

export type CredMetric = 'attempts' | 'ip_fanout'

const EMPTY = '‹empty›'

/**
 * Neutralize one attacker-controlled credential string for display. Usernames
 * and passwords are captured verbatim, so they can hide a C2 host (e.g.
 * `http://1.2.3.4/x` in a password) or bidi/control code points that visually
 * spoof the credential. Compose order mirrors useTerminalTranscript: sanitize
 * first (escape control/bidi as \xHH), then blot IP literals. allowWhitespace
 * is false -- credentials are single-line tokens. Blank stays blank so callers
 * can swap in the empty-marker, which is never run through the sanitizer.
 */
function cleanCred(raw: string): string {
  if (raw === '') return ''
  const escaped = sanitizeAttackerText(raw, { mode: 'escape', allowWhitespace: false })
  return redactIps(escaped).text
}

/**
 * At/above this many distinct source IPs, a single credential reads as a
 * distributed botnet sharing one hardcoded entry (the Mirai signature) rather
 * than one host grinding a wordlist.
 */
const DISTRIBUTED_IP_MIN = 5

/** Bar/segment width with a 2% floor so any non-zero value stays visible. */
export function pctWidth(value: number, max: number): string {
  if (max <= 0 || value <= 0) return '0%'
  return `${Math.max(2, Math.round((value / max) * 100))}%`
}

interface CredRow {
  key: string
  /** Username (or the empty-marker). */
  label: string
  /** ":password" for pair rows, null when grouping by username. */
  sub: string | null
  value: number
  valueLabel: string
  widthPct: string
  /** ip_fanout only: a credential spread across many source IPs (botnet). */
  emphasis: boolean
  title: string
}

/** Build the hero leaderboard rows for the chosen ranking metric. */
export function buildCredentialRows(items: TopCredentialResponse[], metric: CredMetric): CredRow[] {
  const fanout = metric === 'ip_fanout'
  let max = 0
  for (const it of items) {
    const v = fanout ? (it.distinct_ips ?? 0) : it.count
    if (v > max) max = v
  }
  return items.map((it, idx) => {
    const hasUser = it.username !== null && it.username !== undefined
    const hasPass = it.password !== null && it.password !== undefined
    const user = cleanCred(it.username ?? '')
    const pass = cleanCred(it.password ?? '')
    // Primary label is the username, except in the password-only view (no
    // username) where the password itself is the label. The ":password" sub
    // shows only in the pair view (both present).
    const label = hasUser ? user || EMPTY : pass || EMPTY
    const sub = hasUser && hasPass ? `:${pass || EMPTY}` : null
    const cred = sub ? `${label}${sub}` : label
    const ips = it.distinct_ips ?? 0
    const value = fanout ? ips : it.count
    const emphasis = fanout && ips >= DISTRIBUTED_IP_MIN
    const valueLabel = fanout ? `${fmtNumber(ips)} IP${ips === 1 ? '' : 's'}` : fmtNumber(it.count)
    const title = fanout
      ? `${cred} — tried by ${fmtNumber(ips)} IP${ips === 1 ? '' : 's'} (${fmtNumber(it.count)} attempts)`
      : `${cred} — ${fmtNumber(it.count)} attempts`
    return {
      key: `${it.username ?? ''}|${it.password ?? ''}|${idx}`,
      label,
      sub,
      value,
      valueLabel,
      widthPct: pctWidth(value, max),
      emphasis,
      title,
    }
  })
}

export interface BarRow {
  key: string
  label: string
  count: number
  widthPct: string
  title: string
}

/** Flat "user:pass" leaderboard rows (the accepted-credentials mini list). */
export function buildPairBarRows(items: TopCredentialResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it, idx) => {
    const label = `${cleanCred(it.username ?? '') || EMPTY}:${cleanCred(it.password ?? '') || EMPTY}`
    return {
      key: `${label}|${idx}`,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: `${label} — ${fmtNumber(it.count)} attempts`,
    }
  })
}

/**
 * Single-field credential rows (username-only or password-only), sanitized.
 * Used by the Countries detail panel, which scopes `/top-credentials` to one
 * country with `by=password` / `by=username`; the unused field is null. Shares
 * cleanCred so per-country creds get the same control/bidi + IP-literal scrub
 * as the Credentials page.
 */
export function buildCredentialFieldRows(
  items: TopCredentialResponse[],
  field: 'username' | 'password',
): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it, idx) => {
    const raw = field === 'username' ? it.username : it.password
    const label = cleanCred(raw ?? '') || EMPTY
    return {
      key: `${raw ?? ''}|${idx}`,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: `${label} — ${fmtNumber(it.count)} attempts`,
    }
  })
}

const CHARSET_LABELS: Record<string, string> = {
  empty: 'Empty',
  symbol: 'Has symbol',
  digits: 'Digits only',
  lower: 'Lowercase only',
  upper: 'Uppercase only',
  alnum: 'Letters + digits',
}

/** Map top-passwords (the length drill-down) onto display-ready bar rows. */
export function buildPasswordRows(items: TopPasswordResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it, idx) => {
    const label = cleanCred(it.password ?? '') || EMPTY
    return {
      key: `${it.password ?? ''}|${idx}`,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: `${label} — ${fmtNumber(it.count)} attempts`,
    }
  })
}

/** Map the charset-class breakdown onto display-ready bar rows. */
export function buildCharsetRows(classes: CharsetClassResponse[]): BarRow[] {
  let max = 0
  for (const c of classes) if (c.count > max) max = c.count
  return classes.map((c) => {
    const label = CHARSET_LABELS[c.name] ?? c.name
    return {
      key: c.name,
      label,
      count: c.count,
      widthPct: pctWidth(c.count, max),
      title: `${label} — ${fmtNumber(c.count)}`,
    }
  })
}

export interface LengthBar {
  key: string
  length: number
  /** Sparse axis label ('' for unlabeled bars; "{cap}+" for the tail). */
  label: string
  count: number
  heightPct: string
  title: string
}

/**
 * Dense 0..cap length histogram (gaps filled with zero bars) so the x-axis is
 * continuous. The top bucket (== cap) is the ">= cap" tail, labeled "{cap}+".
 */
export function buildLengthBars(
  lengths: CredentialLengthResponse[],
  cappedAt: number,
): LengthBar[] {
  const byLen = new Map<number, number>()
  for (const l of lengths) byLen.set(l.length, (byLen.get(l.length) ?? 0) + l.count)
  let max = 0
  for (const c of byLen.values()) if (c > max) max = c
  const labelAt = new Set([1, Math.round(cappedAt / 2), cappedAt])
  const bars: LengthBar[] = []
  for (let n = 0; n <= cappedAt; n++) {
    const count = byLen.get(n) ?? 0
    const lenLabel = n === cappedAt ? `${cappedAt}+` : String(n)
    const heightPct =
      max > 0 && count > 0 ? `${Math.max(2, Math.round((count / max) * 100))}%` : '0%'
    bars.push({
      key: `len-${n}`,
      length: n,
      label: labelAt.has(n) ? lenLabel : '',
      count,
      heightPct,
      title: `${lenLabel} chars — ${fmtNumber(count)}`,
    })
  }
  return bars
}

/** Accept-rate label; a dash when there is nothing to divide. */
export function fmtSuccessRate(rate: number | null): string {
  if (rate === null) return '—'
  return `${rate.toFixed(rate < 10 ? 2 : 1)}%`
}
