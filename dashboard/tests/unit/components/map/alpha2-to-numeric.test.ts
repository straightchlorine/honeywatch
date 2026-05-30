import { describe, expect, it } from 'vitest'

import { ALPHA2_TO_NUMERIC } from '@/components/map/alpha2-to-numeric'

describe('ALPHA2_TO_NUMERIC', () => {
  it('maps known alpha-2 codes to zero-padded numeric ISO ids', () => {
    // The join-trap guard: world-atlas TopoJSON ids are zero-padded strings,
    // so the table values must be too. AF -> "004", not "4".
    expect(ALPHA2_TO_NUMERIC.AF).toBe('004')
    expect(ALPHA2_TO_NUMERIC.US).toBe('840')
    expect(ALPHA2_TO_NUMERIC.CN).toBe('156')
  })

  it('emits every value as a 3-character numeric string', () => {
    for (const [alpha2, numeric] of Object.entries(ALPHA2_TO_NUMERIC)) {
      expect(alpha2, `${alpha2} key`).toMatch(/^[A-Z]{2}$/)
      expect(numeric, `${alpha2} -> ${numeric}`).toMatch(/^\d{3}$/)
    }
  })

  it('covers the full ISO 3166-1 set and is frozen', () => {
    expect(Object.keys(ALPHA2_TO_NUMERIC).length).toBeGreaterThan(240)
    expect(Object.isFrozen(ALPHA2_TO_NUMERIC)).toBe(true)
  })
})
