import { describe, expect, it } from 'vitest'

import { hexPoints } from '@/utils/hex'

describe('hexPoints', () => {
  it('returns 6 comma-separated points', () => {
    const pts = hexPoints(10, 10, 5)
    expect(pts.split(' ')).toHaveLength(6)
    for (const p of pts.split(' ')) expect(p.split(',')).toHaveLength(2)
  })

  it('places every vertex at radius r from the center', () => {
    const cx = 10
    const cy = 11
    const r = 9
    for (const p of hexPoints(cx, cy, r).split(' ')) {
      const [x, y] = p.split(',').map(Number)
      const d = Math.hypot(x! - cx, y! - cy)
      expect(d).toBeCloseTo(r, 1)
    }
  })

  it('is deterministic for the same inputs', () => {
    expect(hexPoints(1, 2, 3)).toBe(hexPoints(1, 2, 3))
  })
})
