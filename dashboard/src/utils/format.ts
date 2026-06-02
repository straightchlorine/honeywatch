/**
 * The single number formatter for the whole dashboard -- every count goes
 * through here, never a raw `.toLocaleString`. Non-finite input (undefined /
 * null / NaN, e.g. a field a stale API hasn't sent yet) renders as an em dash
 * instead of throwing, so one missing field can never blank the page.
 */
export function fmtNumber(n: number | null | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString('en') : '—'
}

export function fmtDelta(t: { delta: number; pct_change: number | null }): string {
  const sign = t.delta > 0 ? '+' : t.delta < 0 ? '-' : ''
  const abs = fmtNumber(Math.abs(t.delta))
  if (t.pct_change === null) return `${sign}${abs}`
  const pct = Math.abs(t.pct_change).toFixed(1)
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
