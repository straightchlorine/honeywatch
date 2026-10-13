import { describe, expect, it } from 'vitest'

import { buildStory, OUTCOME_TEXT, outcomeBadge, scoreFrac } from '@/utils/sessionStory'

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

describe('OUTCOME_TEXT', () => {
  it('words every session category, and no two alike', () => {
    const words = Object.values(OUTCOME_TEXT)
    expect(Object.keys(OUTCOME_TEXT).sort()).toEqual(['active', 'failed', 'login', 'probe'])
    expect(new Set(words).size).toBe(words.length)
  })
})

describe('outcomeBadge', () => {
  it('gives every outcome an icon and its spelled-out meaning as the title', () => {
    for (const c of Object.keys(OUTCOME_TEXT) as (keyof typeof OUTCOME_TEXT)[]) {
      const b = outcomeBadge(c)
      expect(b.glyph).toBeTruthy()
      expect(b.title).toBe(OUTCOME_TEXT[c])
    }
  })

  it('reuses the rows icons for control and failed', () => {
    expect(outcomeBadge('login').glyph).toBe('key')
    expect(outcomeBadge('failed').glyph).toBe('login')
    expect(outcomeBadge('failed').label).toBe('failed')
  })

  it('gives a probe the eye chip with its spelled-out meaning', () => {
    expect(outcomeBadge('probe')).toEqual({
      label: 'probe',
      glyph: 'eye',
      tone: 'dim',
      title: 'Connected, never tried to log in',
    })
  })
})

describe('buildStory', () => {
  const quiet = { n_commands: 0, n_downloads: 0, n_tcpip: 0 }

  it('shows a probe as a probe, not as a login', () => {
    expect(buildStory({ ...quiet, auth_success: false, category: 'probe' })).toEqual([
      {
        label: 'probe',
        glyph: 'eye',
        tone: 'dim',
        title: 'Connected, never tried to log in',
      },
    ])
  })

  it('shows a failed login as failed, not as login only', () => {
    expect(buildStory({ ...quiet, auth_success: false, category: 'failed' })).toEqual([
      {
        label: 'failed',
        glyph: 'login',
        tone: 'bad',
        title: 'Tried to log in, never got in',
      },
    ])
  })
})
