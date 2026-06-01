import type { ActivityBucketResponse, HeatmapPointResponse } from '@/api/generated/types.gen'
import { WEEKDAY_LABELS } from './heatmapGrid'

const EMPTY = '—'

export interface Kpi {
  /** Display value, or the em-dash placeholder when there is no data. */
  value: string
  /** Session count backing the value (0 when empty). */
  count: number
}

/** Index of the first maximum (strict `>` so ties resolve to the earliest). */
function argmax(arr: number[]): { idx: number; count: number } {
  let idx = 0
  let count = arr[0] ?? 0
  for (let i = 1; i < arr.length; i++) {
    if (arr[i]! > count) {
      count = arr[i]!
      idx = i
    }
  }
  return { idx, count }
}

/** Hour-of-day (UTC) with the most sessions summed across every weekday. */
export function busiestHour(points: HeatmapPointResponse[]): Kpi {
  const byHour = new Array<number>(24).fill(0)
  for (const p of points) {
    if (p.hour < 0 || p.hour > 23) continue
    byHour[p.hour]! += p.count
  }
  const { idx, count } = argmax(byHour)
  if (count <= 0) return { value: EMPTY, count: 0 }
  return { value: `${String(idx).padStart(2, '0')}:00`, count }
}

/** Weekday (0=Sun) with the most sessions summed across every hour. */
export function busiestWeekday(points: HeatmapPointResponse[]): Kpi {
  const byDay = new Array<number>(7).fill(0)
  for (const p of points) {
    if (p.weekday < 0 || p.weekday > 6) continue
    byDay[p.weekday]! += p.count
  }
  const { idx, count } = argmax(byDay)
  if (count <= 0) return { value: EMPTY, count: 0 }
  return { value: WEEKDAY_LABELS[idx]!, count }
}

/** Calendar day with the most sessions, from the daily activity buckets. */
export function peakDay(buckets: ActivityBucketResponse[]): Kpi {
  let best: ActivityBucketResponse | null = null
  for (const b of buckets) {
    if (!best || b.count > best.count) best = b
  }
  if (!best || best.count <= 0) return { value: EMPTY, count: 0 }
  return { value: fmtShortDate(best.bucket), count: best.count }
}

/** Short UTC date label (e.g. "May 24"); buckets are date_trunc'd in UTC. */
function fmtShortDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return EMPTY
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}
