export function fmtNumber(n: number): string {
  return n.toLocaleString('en')
}

export function fmtDelta(t: { delta: number; pct_change: number | null }): string {
  const sign = t.delta > 0 ? '+' : t.delta < 0 ? '-' : ''
  const abs = Math.abs(t.delta).toLocaleString('en')
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

export function fmtDateTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}

export function bucketKey(iso: string, granularity: 'minute' | 'hour' | 'day'): string {
  const d = new Date(iso)
  if (granularity === 'day') {
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  }
  if (granularity === 'hour') {
    return d.toLocaleString('en', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    })
  }
  return d.toLocaleString('en', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}
