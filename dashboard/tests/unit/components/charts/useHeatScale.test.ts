import { describe, expect, it } from 'vitest'

import { HEAT_FLOOR, rampColor, useHeatScale } from '@/components/charts/useHeatScale'

describe('useHeatScale', () => {
  it('returns the zero color for empty data and max 0', () => {
    const s = useHeatScale([], { zeroColor: 'var(--bg-2)' })
    expect(s.max).toBe(0)
    expect(s.fill(0)).toBe('var(--bg-2)')
    expect(s.rampStops).toHaveLength(0)
  })

  it('defaults the zero color to --bg-2', () => {
    expect(useHeatScale([5]).fill(0)).toBe('var(--bg-2)')
  })

  it('paints positive counts with the amber color-mix ramp and keeps the floor above zero', () => {
    const s = useHeatScale([1, 100, 1000])
    expect(s.max).toBe(1000)
    expect(s.fill(1000)).toContain('color-mix')
    expect(s.fill(1)).toContain('color-mix')
    expect(s.fill(1)).not.toBe('var(--bg-2)')
  })

  it('exposes legend ramp stops when data exists', () => {
    const s = useHeatScale([50])
    expect(s.rampStops.length).toBeGreaterThan(1)
    for (const stop of s.rampStops) expect(stop).toContain('color-mix')
  })

  it('rampColor clamps out-of-range intensities to the two ramp ends', () => {
    expect(rampColor(-1)).toContain('var(--accent-dim)')
    expect(rampColor(2)).toContain('var(--warning)')
    expect(HEAT_FLOOR).toBe(0.15)
  })
})
