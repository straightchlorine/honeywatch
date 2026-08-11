/**
 * Central formatter for dashboard counts—never raw toLocaleString.
 * Non-finite (null/undefined/NaN) renders '—' so missing fields don't break layout.
 */
export function fmtNumber(n: number | null | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('en') : '—'
}

/**
 * Compact notation for KPI trend delta: '16.1k', '1.8M'.
 * Below 1000 uses fmtNumber (preserves thousands separators). Keeps trend delta on one line.
 */
export function fmtCompact(n: number | null | undefined): string {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '—'
  const abs = Math.abs(n)
  if (abs < 1000) return fmtNumber(n)
  let value: number
  let suffix: string
  if (abs >= 1e9) {
    value = n / 1e9
    suffix = 'B'
  } else if (abs >= 1e6) {
    value = n / 1e6
    suffix = 'M'
  } else {
    value = n / 1e3
    suffix = 'k'
  }
  // One decimal, but drop a trailing ".0" so 2000 reads "2k" not "2.0k".
  return `${value.toFixed(1).replace(/\.0$/, '')}${suffix}`
}

export function fmtDelta(t: { delta: number; pct_change: number | null }): string {
  const sign = t.delta > 0 ? '+' : t.delta < 0 ? '-' : ''
  const abs = fmtCompact(Math.abs(t.delta))
  if (t.pct_change === null) return `${sign}${abs}`
  // Keep small percentages precise (12.5%) but compact the runaway ones a
  // honeypot produces from a near-empty prior window (1822.8% -> 1.8k%).
  const p = Math.abs(t.pct_change)
  const pct = p >= 1000 ? fmtCompact(p) : p >= 100 ? String(Math.round(p)) : p.toFixed(1)
  return `${sign}${abs} (${sign}${pct}%)`
}

export function fmtRelativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diffSec = Math.round((now - then) / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.round(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.round(diffH / 24)
  return `${diffD}d ago`
}
