import { describe, expect, it } from 'vitest'

import { ALPHA2_TO_NUMERIC } from '@/components/map/alpha2-to-numeric'
import { NUMERIC_TO_ALPHA2 } from '@/components/map/numeric-to-alpha2'

describe('NUMERIC_TO_ALPHA2', () => {
  it('inverts the alpha2 -> numeric table (US <-> 840, CN <-> 156)', () => {
    expect(NUMERIC_TO_ALPHA2['840']).toBe('US')
    expect(NUMERIC_TO_ALPHA2['156']).toBe('CN')
    // Sub-100 ids keep their zero padding (the string-join invariant).
    expect(NUMERIC_TO_ALPHA2['004']).toBe('AF')
  })

  it('round-trips every alpha2 code back to itself', () => {
    for (const [a2, num] of Object.entries(ALPHA2_TO_NUMERIC)) {
      expect(NUMERIC_TO_ALPHA2[num]).toBe(a2)
    }
  })
})
