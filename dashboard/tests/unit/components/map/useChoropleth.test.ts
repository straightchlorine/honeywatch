import { describe, expect, it } from 'vitest'

import { useChoropleth } from '@/components/map/useChoropleth'

describe('useChoropleth', () => {
  it('returns the land color for zero/unknown counts and max 0 when empty', () => {
    const c = useChoropleth(new Map())
    expect(c.max).toBe(0)
    expect(c.fill('840')).toBe('var(--map-land)')
    expect(c.rampStops).toHaveLength(0)
  })

  it('computes the max and paints data countries with the amber ramp', () => {
    const c = useChoropleth(
      new Map([
        ['156', 1200],
        ['840', 400],
      ]),
    )
    expect(c.max).toBe(1200)
    // Data countries use the token color-mix ramp; absent ones stay land.
    expect(c.fill('156')).toContain('color-mix')
    expect(c.fill('840')).toContain('color-mix')
    expect(c.fill('999')).toBe('var(--map-land)')
  })

  it('keeps the lowest data color above the no-data land color (amber floor)', () => {
    const c = useChoropleth(new Map([['004', 1]]))
    const lowest = c.fill('004')
    // count=1 still renders a visible amber tint, never the land color.
    expect(lowest).toContain('color-mix')
    expect(lowest).not.toBe('var(--map-land)')
  })

  it('exposes ramp stops for the legend gradient when data exists', () => {
    const c = useChoropleth(new Map([['156', 50]]))
    expect(c.rampStops.length).toBeGreaterThan(1)
    for (const stop of c.rampStops) expect(stop).toContain('color-mix')
  })
})
