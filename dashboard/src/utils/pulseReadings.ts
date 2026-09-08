import type { HeatmapGrid } from './heatmapGrid'

/** Weekday plural labels indexed like `HeatmapGrid.grid`: 0=Sun..6=Sat. */
const DAY_PLURAL = [
  'Sundays',
  'Mondays',
  'Tuesdays',
  'Wednesdays',
  'Thursdays',
  'Fridays',
  'Saturdays',
] as const

/** Weekday singular labels, indexed like `HeatmapGrid.grid`: 0=Sun..6=Sat. */
const DAY_SINGULAR = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
] as const

/** Minimum sessions to report readings; prevents "600% above average" nonsense from handful of hits. */
const MIN_SESSIONS_FOR_READINGS = 50

/** Index of the first maximum (strict `>` so ties resolve to the earliest). */
function argmax(arr: readonly number[]): number {
  let idx = 0
  for (let i = 1; i < arr.length; i++) {
    if (arr[i]! > arr[idx]!) idx = i
  }
  return idx
}

/**
 * Plain-English "readings" for the Pulse card: computed deterministically from
 * the heatmap grid using a candidate-with-complement structure. Returns plain
 * ASCII sentences (no markup - callers interpolate, never v-html, per the
 * untrusted-string invariant).
 *
 * Candidate pairs, in priority order:
 *   1. PEAK WINDOW: busiest contiguous 6-hour band and its share (primary if > 26%)
 *   2. WEEKDAY LIFT: busiest weekday vs weekly mean (primary if >= 5% and not tied)
 *   3. WEEKEND VS WEEKDAY: weekend vs weekday activity (primary if >= 5% difference)
 *   4. BUSIEST CELL: single cell with highest count (fallback)
 *
 * Returns [] if total sessions below MIN_SESSIONS_FOR_READINGS threshold.
 */
export function pulseReadings(heatmap: HeatmapGrid): string[] {
  const { grid } = heatmap

  let total = 0
  for (const row of grid) for (const n of row) total += n
  if (total < MIN_SESSIONS_FOR_READINGS) return []

  const byDay = new Array<number>(7).fill(0)
  for (let w = 0; w < 7; w++) {
    for (let h = 0; h < 24; h++) {
      byDay[w]! += grid[w]![h]!
    }
  }

  let bestSum = 0
  let bestHour = 0
  for (let startHour = 0; startHour < 24; startHour++) {
    let sum = 0
    for (let offset = 0; offset < 6; offset++) {
      const hour = (startHour + offset) % 24
      for (let w = 0; w < 7; w++) {
        sum += grid[w]![hour]!
      }
    }
    if (sum > bestSum) {
      bestSum = sum
      bestHour = startHour
    }
  }
  const peakPercentage = Math.round((bestSum / total) * 100)

  const dayMean = byDay.reduce((a, b) => a + b, 0) / 7
  const topDay = dayMean > 0 ? argmax(byDay) : 0
  const tied = dayMean > 0 && byDay.filter((n) => n === byDay[topDay]!).length > 1
  const weekdayLift = dayMean > 0 ? Math.round((byDay[topDay]! / dayMean - 1) * 100) : 0

  const weekendSum = byDay[0]! + byDay[6]!
  const weekdaySum = byDay[1]! + byDay[2]! + byDay[3]! + byDay[4]! + byDay[5]!
  const weekendMean = weekendSum / 2
  const weekdayMean = weekdaySum / 5
  const weekendDiff = weekdayMean > 0 ? Math.abs(weekendMean - weekdayMean) / weekdayMean * 100 : 0
  const weekendDiffPercent = Math.round(weekendDiff)

  let busiestValue = 0
  let busiestDay = 0
  let busiestHour = 0
  for (let w = 0; w < 7; w++) {
    for (let h = 0; h < 24; h++) {
      if (grid[w]![h]! > busiestValue) {
        busiestValue = grid[w]![h]!
        busiestDay = w
        busiestHour = h
      }
    }
  }

  const candidates: Array<() => string | null> = [
    () => {
      if (peakPercentage > 26) {
        let phrase = 'Roughly a quarter'
        if (peakPercentage >= 60) phrase = 'Well over half'
        else if (peakPercentage >= 50) phrase = 'More than half'
        else if (peakPercentage >= 45) phrase = 'Just under half'
        else if (peakPercentage >= 38) phrase = 'More than a third'
        else if (peakPercentage >= 30) phrase = 'About a third'

        const endHour = (bestHour + 6) % 24
        const startStr = `${String(bestHour).padStart(2, '0')}:00`
        const endStr = `${String(endHour).padStart(2, '0')}:00`

        return `${phrase} of all sessions (${peakPercentage}%) arrive between ${startStr} and ${endStr} UTC.`
      } else {
        return `Sessions are spread evenly through the day - the busiest six hours hold only ${peakPercentage}% of them.`
      }
    },

    () => {
      if (dayMean > 0) {
        if (weekdayLift >= 5 && !tied) {
          return `${DAY_PLURAL[topDay]} run ${weekdayLift}% above the weekly average.`
        }
        // A tie is not the same story as a flat week: several days can share a
        // real lift. Saying "the busiest is only 21% above" would contradict
        // itself, so name the tie instead.
        if (tied && weekdayLift >= 5) {
          const tiedCount = byDay.filter((n) => n === byDay[topDay]!).length
          return `${tiedCount} days tie for the busiest, each ${weekdayLift}% above the weekly average.`
        }
        if (weekdayLift <= 0) {
          return 'No weekday stands out - every day carries about the same load.'
        }
        return `No weekday stands out - the busiest is only ${weekdayLift}% above the weekly average.`
      }
      return null
    },

    () => {
      if (weekdayMean > 0) {
        if (weekendDiffPercent >= 5) {
          if (weekendMean < weekdayMean) {
            return `Weekends are ${weekendDiffPercent}% quieter than weekdays.`
          } else {
            return `Weekends are ${weekendDiffPercent}% busier than weekdays.`
          }
        } else {
          return `Weekends and weekdays run at about the same rate.`
        }
      }
      return null
    },

    () => {
      if (busiestValue > 0) {
        const hourStr = `${String(busiestHour).padStart(2, '0')}:00`
        return `The single busiest hour of the week is ${DAY_SINGULAR[busiestDay]} at ${hourStr} UTC.`
      }
      return null
    },
  ]

  const readings: string[] = []
  for (const candidate of candidates) {
    const reading = candidate()
    if (reading !== null) {
      readings.push(reading)
      if (readings.length === 3) break
    }
  }

  return readings
}
