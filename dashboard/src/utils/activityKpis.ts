import type { ActivityBucketResponse, HeatmapPointResponse } from '@/api/generated/types.gen'
import { WEEKDAY_LABELS } from './heatmapGrid'
import { fmtUtcDate } from './format'

const EMPTY = '-'

export interface Kpi {
  /** Display value; placeholder when no data. */
  value: string
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

/** Index of the first maximum, or -1 when nothing is above zero (nothing to highlight). */
export function peakIndex(values: number[]): number {
  const { idx, count } = argmax(values)
  return count > 0 ? idx : -1
}

/** Sessions per hour of day (UTC), summed across every weekday. Always 24 entries. */
export function hourlyTotals(points: HeatmapPointResponse[]): number[] {
  const byHour = new Array<number>(24).fill(0)
  for (const p of points) {
    if (p.hour < 0 || p.hour > 23) continue
    byHour[p.hour]! += p.count
  }
  return byHour
}

/** Sessions per weekday (0=Sun), summed across every hour. Always 7 entries. */
export function weekdayTotals(points: HeatmapPointResponse[]): number[] {
  const byDay = new Array<number>(7).fill(0)
  for (const p of points) {
    if (p.weekday < 0 || p.weekday > 6) continue
    byDay[p.weekday]! += p.count
  }
  return byDay
}

/** Hour-of-day (UTC) with the most sessions summed across every weekday. */
export function busiestHour(points: HeatmapPointResponse[]): Kpi {
  const { idx, count } = argmax(hourlyTotals(points))
  if (count <= 0) return { value: EMPTY, count: 0 }
  return { value: `${String(idx).padStart(2, '0')}:00`, count }
}

/** Weekday (0=Sun) with the most sessions summed across every hour. */
export function busiestWeekday(points: HeatmapPointResponse[]): Kpi {
  const { idx, count } = argmax(weekdayTotals(points))
  if (count <= 0) return { value: EMPTY, count: 0 }
  return { value: WEEKDAY_LABELS[idx]!, count }
}

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
  return fmtUtcDate(d)
}

/** Largest count and the lower median of the counts; both 0 when empty. */
export function peakAndTypical(counts: number[]): { peak: number; typical: number } {
  const v = [...counts].sort((a, b) => a - b)
  return { peak: v.at(-1) ?? 0, typical: v.length ? v[Math.floor((v.length - 1) / 2)]! : 0 }
}
