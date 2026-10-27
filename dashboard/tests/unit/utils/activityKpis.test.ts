import { describe, expect, it } from 'vitest'

import {
  busiestHour,
  busiestWeekday,
  hourlyTotals,
  peakAndTypical,
  peakDay,
  peakIndex,
  weekdayTotals,
} from '@/utils/activityKpis'

describe('activityKpis', () => {
  it('busiestHour sums across weekdays and formats HH:00', () => {
    const r = busiestHour([
      { weekday: 0, hour: 14, count: 3 },
      { weekday: 1, hour: 14, count: 4 },
      { weekday: 2, hour: 9, count: 5 },
    ])
    expect(r.value).toBe('14:00')
    expect(r.count).toBe(7)
  })

  it('busiestWeekday sums across hours (0=Sun)', () => {
    const r = busiestWeekday([
      { weekday: 0, hour: 1, count: 2 },
      { weekday: 0, hour: 2, count: 2 },
      { weekday: 3, hour: 1, count: 3 },
    ])
    expect(r.value).toBe('Sun')
    expect(r.count).toBe(4)
  })

  it('resolves ties to the earliest bucket', () => {
    const r = busiestHour([
      { weekday: 0, hour: 2, count: 5 },
      { weekday: 0, hour: 8, count: 5 },
    ])
    expect(r.value).toBe('02:00')
  })

  it('peakDay picks the highest day bucket and formats a UTC short date', () => {
    const r = peakDay([
      { bucket: '2026-05-23T00:00:00+00:00', count: 4 },
      { bucket: '2026-05-24T00:00:00+00:00', count: 9 },
    ])
    expect(r.count).toBe(9)
    expect(r.value).toBe('May 24')
  })

  it('returns the dash placeholder for empty inputs', () => {
    expect(busiestHour([]).value).toBe('-')
    expect(busiestWeekday([]).value).toBe('-')
    expect(peakDay([]).value).toBe('-')
  })

  it('hourlyTotals and weekdayTotals sum into fixed-size arrays and skip out-of-range points', () => {
    const pts = [
      { weekday: 0, hour: 14, count: 3 },
      { weekday: 1, hour: 14, count: 4 },
      { weekday: 6, hour: 0, count: 1 },
      { weekday: 9, hour: 30, count: 50 },
    ]
    const hours = hourlyTotals(pts)
    expect(hours).toHaveLength(24)
    expect(hours[14]).toBe(7)
    expect(hours[0]).toBe(1)
    const days = weekdayTotals(pts)
    expect(days).toHaveLength(7)
    expect(days).toEqual([3, 4, 0, 0, 0, 0, 1])
  })

  it('peakIndex returns the first maximum, or -1 when everything is zero', () => {
    expect(peakIndex([1, 5, 5, 2])).toBe(1)
    expect(peakIndex([0, 0])).toBe(-1)
    expect(peakIndex([])).toBe(-1)
  })

  it.each([
    [[], 0, 0],
    [[5], 5, 5],
    [[1, 2, 3, 100], 100, 2],
    [[0, 0], 0, 0],
  ])('peakAndTypical(%j) -> peak %i typical %i', (counts, peak, typical) => {
    expect(peakAndTypical(counts)).toEqual({ peak, typical })
  })
})
