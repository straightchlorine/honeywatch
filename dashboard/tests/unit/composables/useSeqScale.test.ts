import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { inkContrast, inkFor, logT, seq, useSeqScale } from '@/composables/useSeqScale'

// Run from the dashboard root (vitest default), so cwd-relative is the token file.
const tokensCss = readFileSync(resolve(process.cwd(), 'src/assets/tokens.css'), 'utf8')

function tokenValue(name: string): string {
  return tokensCss.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`))?.[1] ?? ''
}

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

describe('inkContrast', () => {
  it('matches a hand-computed WCAG ratio (black on seq(0) is about 2.31:1)', () => {
    expect(inkContrast('#000000', 0)).toBeCloseTo(2.31, 1)
  })
})

describe('inkFor', () => {
  it('lights the dark end, darkens the bright end', () => {
    expect(inkFor(0)).toBe('#f5e6c8')
    expect(inkFor(1)).toBe('#120d09')
  })

  it('stays in sync with the --text and --bg-0 tokens', () => {
    expect(inkFor(0)).toBe(tokenValue('--text'))
    expect(inkFor(1)).toBe(tokenValue('--bg-0'))
  })

  it('reaches WCAG AA (4.5:1) at every point on the ramp', () => {
    for (let t = 0; t <= 1.0001; t += 0.01) {
      expect(inkContrast(inkFor(t), t)).toBeGreaterThanOrEqual(4.5)
    }
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
