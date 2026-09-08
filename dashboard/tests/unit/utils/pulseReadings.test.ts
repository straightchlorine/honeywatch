import { describe, expect, it } from 'vitest'

import type { HeatmapPointResponse } from '@/api/generated/types.gen'
import { buildHeatmapGrid } from '@/utils/heatmapGrid'
import { pulseReadings } from '@/utils/pulseReadings'

describe('pulseReadings', () => {
  it('returns empty array for empty heatmap', () => {
    expect(pulseReadings(buildHeatmapGrid([]))).toEqual([])
  })

  it('returns empty array when total sessions below threshold', () => {
    const points: HeatmapPointResponse[] = [
      { weekday: 1, hour: 10, count: 30 },
      { weekday: 2, hour: 15, count: 15 },
    ]
    expect(pulseReadings(buildHeatmapGrid(points))).toEqual([])
  })

  it('does not emit "0.Nx" style sentences', () => {
    const points: HeatmapPointResponse[] = []
    for (let w = 1; w <= 5; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 5 })
      }
    }
    for (const w of [0, 6]) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 1 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    for (const reading of readings) {
      expect(reading).not.toMatch(/\b0\.\d+x\b/)
    }
  })

  it('emits complement for perfectly flat week instead of weekday-lift primary', () => {
    const points: HeatmapPointResponse[] = []
    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 1 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    const hasComplementReading = readings.some(
      (s) => s.includes('No weekday stands out') || s.includes('tie for the busiest'),
    )
    expect(hasComplementReading).toBe(true)
    const hasWinnerReading = readings.some(s => s.match(/^(Sundays|Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays) run/))
    expect(hasWinnerReading).toBe(false)
  })

  it('emits complement for perfectly flat week instead of weekend/weekday primary', () => {
    const points: HeatmapPointResponse[] = []
    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 1 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    const hasWeekendComparison = readings.some(
      s => s.includes('quieter') || s.includes('busier')
    )
    expect(hasWeekendComparison).toBe(false)
    const hasComplementReading = readings.some(s => s.includes('Weekends and weekdays run at about the same rate'))
    expect(hasComplementReading).toBe(true)
  })

  it('produces all three sentences with realistic peaky grid', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 1; w <= 5; w++) {
      for (let h = 16; h <= 21; h++) {
        points.push({ weekday: w, hour: h, count: 8 })
      }
    }

    for (const w of [0, 6]) {
      for (let h = 10; h <= 14; h++) {
        points.push({ weekday: w, hour: h, count: 3 })
      }
    }

    points.push({ weekday: 3, hour: 12, count: 50 })

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings.length).toBe(3)
    expect(readings[0]).toContain('of all sessions')
    expect(readings[0]).toContain('arrive between')
    expect(readings[0]).not.toContain('NaN')
    expect(readings[0]).not.toContain('Infinity')

    expect(readings[1]).toContain('run')
    expect(readings[1]).toContain('%')
    expect(readings[1]).toContain('above')

    expect(readings[2]).toContain('quieter')
    expect(readings[2]).not.toContain('busier')
  })

  it('emits "quieter" when weekends have fewer sessions than weekdays', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 1; w <= 5; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 10 })
      }
    }

    for (const w of [0, 6]) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    const weekendComparison = readings.find(s => s.includes('Weekends'))
    expect(weekendComparison).toBeDefined()
    expect(weekendComparison).toContain('quieter')
    expect(weekendComparison).not.toContain('busier')
  })

  it('emits "busier" when weekends have more sessions than weekdays', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 1; w <= 5; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    for (const w of [0, 6]) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 10 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    const weekendComparison = readings.find(s => s.includes('Weekends'))
    expect(weekendComparison).toBeDefined()
    expect(weekendComparison).toContain('busier')
    expect(weekendComparison).not.toContain('quieter')
  })

  it('produces no NaN or Infinity in output', () => {
    const points: HeatmapPointResponse[] = [
      { weekday: 3, hour: 12, count: 50 },
    ]

    const readings = pulseReadings(buildHeatmapGrid(points))

    for (const reading of readings) {
      expect(reading).not.toContain('NaN')
      expect(reading).not.toContain('Infinity')
      expect(reading).not.toContain('undefined')
    }
  })

  it('handles all-weekend edge case gracefully (no weekday sessions)', () => {
    const points: HeatmapPointResponse[] = []

    for (let h = 0; h < 24; h++) {
      points.push({ weekday: 6, hour: h, count: 5 })
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings).toBeDefined()
    for (const reading of readings) {
      expect(reading).not.toContain('NaN')
      expect(reading).not.toContain('Infinity')
    }
  })

  it('emits complement when peak window share is not meaningfully above 25%', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    const hasPeakPrimary = readings.some(s => s.includes('arrive between'))
    expect(hasPeakPrimary).toBe(false)
    const hasComplementReading = readings.some(s => s.includes('Sessions are spread evenly through the day'))
    expect(hasComplementReading).toBe(true)
  })

  it('emits only valid ASCII characters', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 1; w <= 5; w++) {
      for (let h = 16; h <= 21; h++) {
        points.push({ weekday: w, hour: h, count: 10 })
      }
    }
    for (const w of [0, 6]) {
      for (let h = 10; h <= 14; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }
    points.push({ weekday: 3, hour: 12, count: 50 })

    const readings = pulseReadings(buildHeatmapGrid(points))

    for (const reading of readings) {
      for (let i = 0; i < reading.length; i++) {
        const code = reading.charCodeAt(i)
        expect(code).toBeLessThan(128)
      }
      expect(reading).not.toContain('—')
    }
  })

  it('produces sensible readings with realistic data', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 0; w < 7; w++) {
      for (let h = 18; h <= 23; h++) {
        points.push({ weekday: w, hour: h, count: 15 })
      }
    }

    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 18; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    for (let w = 1; w <= 5; w++) {
      for (let h = 9; h <= 15; h++) {
        points.push({ weekday: w, hour: h, count: w === 3 ? 40 : 15 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings.some(s => s.includes('arrive between'))).toBe(true)
    expect(readings.some(s => s.includes('Wednesdays run'))).toBe(true)

    for (const reading of readings) {
      expect(typeof reading).toBe('string')
      expect(reading.length).toBeGreaterThan(0)
    }
  })

  it('names no busiest weekday when two days tie for the peak', () => {
    const points: HeatmapPointResponse[] = [
      { weekday: 0, hour: 10, count: 50 },
      { weekday: 4, hour: 10, count: 50 },
    ]

    const readings = pulseReadings(buildHeatmapGrid(points))

    // Never name a single winner; ties and flats both emit complements.
    const hasTieReading = readings.some(
      (s) => s.includes('No weekday stands out') || s.includes('tie for the busiest'),
    )
    expect(hasTieReading).toBe(true)
    const hasPrimaryReading = readings.some((s) => s.match(/^(Sundays|Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays) run/))
    expect(hasPrimaryReading).toBe(false)
  })
})

  it('KEY TEST: perfectly flat grid returns exactly 3 complement readings', () => {
    const points: HeatmapPointResponse[] = []
    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 24; h++) {
        points.push({ weekday: w, hour: h, count: 1 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings).toHaveLength(3)
    expect(readings[0]).toBe('Sessions are spread evenly through the day - the busiest six hours hold only 25% of them.')
    expect(readings[1]).toBe('No weekday stands out - every day carries about the same load.')
    expect(readings[2]).toBe('Weekends and weekdays run at about the same rate.')
  })

  it('strongly peaky grid returns exactly 3 primary readings', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 0; w < 7; w++) {
      for (let h = 18; h <= 23; h++) {
        points.push({ weekday: w, hour: h, count: 20 })
      }
    }

    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 18; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    for (let w = 1; w <= 5; w++) {
      const boost = (w === 3) ? 50 : 30
      points.push({ weekday: w, hour: 12, count: boost })
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings).toHaveLength(3)
    expect(readings[0]).toContain('of all sessions')
    expect(readings[0]).toContain('arrive between')
    expect(readings[1]).toContain('Wednesdays run')
    expect(readings[1]).toContain('above the weekly average')
    expect(readings[2]).toContain('Weekends are')
    expect(readings[2]).toContain('quieter')
  })

  it('mixed grid (peaky hour, flat weekday) returns 3 readings correctly', () => {
    const points: HeatmapPointResponse[] = []

    for (let w = 0; w < 7; w++) {
      for (let h = 21; h <= 23; h++) {
        points.push({ weekday: w, hour: h, count: 25 })
      }
    }

    for (let w = 0; w < 7; w++) {
      for (let h = 0; h < 21; h++) {
        points.push({ weekday: w, hour: h, count: 2 })
      }
    }

    const readings = pulseReadings(buildHeatmapGrid(points))

    expect(readings).toHaveLength(3)
    expect(readings[0]).toContain('arrive between')
    expect(readings[1]).toContain('No weekday stands out')
    expect(readings[2]).toContain('Weekends and weekdays run at about the same rate')
  })

describe('pulseReadings weekday ties', () => {
  it('names no busiest weekday when several share the peak', () => {
    const grid = Array.from({ length: 7 }, () => new Array<number>(24).fill(0))
    for (let w = 1; w <= 5; w++) for (let h = 0; h < 24; h++) grid[w]![h] = 20
    for (const w of [0, 6]) for (let h = 0; h < 24; h++) grid[w]![h] = 8
    const out = pulseReadings({ grid, max: 20 })
    expect(
      out.some((r) => r.includes('No weekday stands out') || r.includes('tie for the busiest')),
    ).toBe(true)
    expect(out.some((r) => r.match(/^(Sundays|Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays) run/))).toBe(false)
    expect(out.some((r) => r.includes('Weekends are 60% quieter than weekdays.'))).toBe(true)
  })
})
