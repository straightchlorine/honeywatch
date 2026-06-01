import { describe, expect, it } from 'vitest'

import { sessionClass } from '@/utils/sessionClass'

describe('sessionClass', () => {
  it('maps the active category to a CLI badge with a command-count tooltip', () => {
    const c = sessionClass({ category: 'active', command_count: 3 })
    expect(c.kind).toBe('active')
    expect(c.label).toBe('CLI')
    expect(c.title).toContain('3 commands')
    expect(c.glyph).toBeTruthy()
  })

  it('singularizes a single command in the active tooltip', () => {
    expect(sessionClass({ category: 'active', command_count: 1 }).title).toBe('1 command run')
  })

  it('maps login/failed/probe to their labels (no priority logic)', () => {
    expect(sessionClass({ category: 'login', command_count: 0 }).label).toBe('Login')
    expect(sessionClass({ category: 'failed', command_count: 0 }).label).toBe('Failed auth')
    expect(sessionClass({ category: 'probe', command_count: 0 }).label).toBe('Probe')
  })

  it('gives every category a distinct non-color glyph (WCAG 1.4.1 cue)', () => {
    const glyphs = (['active', 'login', 'failed', 'probe'] as const).map(
      (category) => sessionClass({ category, command_count: 0 }).glyph,
    )
    expect(new Set(glyphs).size).toBe(4)
  })
})
