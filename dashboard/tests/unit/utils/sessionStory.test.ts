import { describe, expect, it } from 'vitest'

import { scoreFrac } from '@/utils/sessionStory'

describe('scoreFrac', () => {
  it('maps the dataset ceiling to exactly 1 (full saturation)', () => {
    expect(scoreFrac(56, 56)).toBe(1)
  })

  it('maps zero interest to 0', () => {
    expect(scoreFrac(0, 56)).toBe(0)
  })

  it('scales proportionally between 0 and the ceiling', () => {
    expect(scoreFrac(28, 56)).toBeCloseTo(0.5)
  })

  it('clamps above 1 if interest somehow exceeds the ceiling', () => {
    expect(scoreFrac(100, 56)).toBe(1)
  })

  it('clamps negative interest to 0', () => {
    expect(scoreFrac(-5, 56)).toBe(0)
  })

  it('never divides by zero when the ceiling is 0 (empty dataset)', () => {
    expect(scoreFrac(10, 0)).toBe(1)
    expect(scoreFrac(0, 0)).toBe(0)
    expect(Number.isFinite(scoreFrac(10, 0))).toBe(true)
  })
})
