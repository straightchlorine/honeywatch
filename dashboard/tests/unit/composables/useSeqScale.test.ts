import { describe, expect, it } from 'vitest'

import { INK_FLIP_T, logT, needsDarkInk, seq, useSeqScale } from '@/composables/useSeqScale'

describe('seq', () => {
  it('maps t=0 to the darkest ramp stop', () => {
    expect(seq(0)).toBe('rgb(120,53,15)')
  })

  it('maps t=1 to the brightest ramp stop', () => {
    expect(seq(1)).toBe('rgb(253,230,138)')
  })

  it('clamps out-of-range input', () => {
    expect(seq(-5)).toBe(seq(0))
    expect(seq(5)).toBe(seq(1))
  })
})

describe('logT', () => {
  it('returns 0 for non-positive values or a non-positive max', () => {
    expect(logT(0, 100)).toBe(0)
    expect(logT(-1, 100)).toBe(0)
    expect(logT(10, 0)).toBe(0)
  })

  it('returns 1 when value equals max', () => {
    expect(logT(100, 100)).toBe(1)
  })

  it('compresses the long tail (heavy-tailed counts stay legible)', () => {
    // A count 10x smaller should map to well over 1/10th of the range.
    expect(logT(10, 1000)).toBeGreaterThan(0.3)
  })
})

describe('needsDarkInk', () => {
  it('stays light-ink below the flip threshold', () => {
    expect(needsDarkInk(INK_FLIP_T - 0.01)).toBe(false)
  })

  it('flips to dark ink at and above the threshold', () => {
    expect(needsDarkInk(INK_FLIP_T)).toBe(true)
    expect(needsDarkInk(INK_FLIP_T + 0.1)).toBe(true)
  })
})

describe('useSeqScale', () => {
  it('colors a value relative to a reactive max', () => {
    const scale = useSeqScale(() => 100)
    expect(scale.color(100)).toBe(seq(1))
    expect(scale.color(0)).toBe(seq(0))
  })

  it('applies the optional power curve', () => {
    const scale = useSeqScale(() => 100)
    expect(scale.color(50, 1.6)).toBe(seq(Math.pow(logT(50, 100), 1.6)))
  })
})
