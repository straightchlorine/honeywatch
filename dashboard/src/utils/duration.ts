/**
 * Human-readable elapsed time between two ISO timestamps, e.g. "58s", "3m 12s",
 * "1h 4m". Returns the em-dash placeholder when either bound is missing or the
 * range is negative/unparseable (sessions cowrie never recorded a close for).
 */
export function humanizeDuration(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (!Number.isFinite(ms) || ms < 0) return '—'

  const totalSec = Math.round(ms / 1000)
  if (totalSec < 60) return `${totalSec}s`

  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min < 60) return sec ? `${min}m ${sec}s` : `${min}m`

  const hr = Math.floor(min / 60)
  const remMin = min % 60
  return remMin ? `${hr}h ${remMin}m` : `${hr}h`
}
