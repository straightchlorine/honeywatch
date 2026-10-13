import { describe, expect, it } from 'vitest'
import { ALL_ROWS, MAIN_ROWS, NONE_ROW, toggleHas } from '@/utils/outcomeFilter'

describe('outcome rows', () => {
  it('MAIN_ROWS lists the four interest tokens in canonical order', () => {
    expect(MAIN_ROWS.map((r) => r.token)).toEqual(['success', 'commands', 'tcpip', 'downloads'])
  })

  it('maps "Got control" to the shell count, not the success token', () => {
    expect(MAIN_ROWS[0]).toMatchObject({
      token: 'success',
      label: 'Got control',
      countKey: 'shell',
    })
  })

  it('NONE_ROW is the none token and stays out of MAIN_ROWS', () => {
    expect(NONE_ROW).toMatchObject({ token: 'none', countKey: 'none' })
    expect(MAIN_ROWS).not.toContain(NONE_ROW)
  })

  it('ALL_ROWS is MAIN_ROWS followed by NONE_ROW', () => {
    expect(ALL_ROWS).toEqual([...MAIN_ROWS, NONE_ROW])
    expect(ALL_ROWS.at(-1)).toBe(NONE_ROW)
  })

  it('gives every row a distinct token and a non-empty label', () => {
    expect(new Set(ALL_ROWS.map((r) => r.token)).size).toBe(ALL_ROWS.length)
    for (const r of ALL_ROWS) expect(r.label.length).toBeGreaterThan(0)
  })

  it('accepts every row token as a single-token value', () => {
    for (const r of ALL_ROWS) expect(toggleHas('', r.token)).toBe(r.token)
  })
})

describe('toggleHas', () => {
  describe('add and remove', () => {
    it('adds a token to an empty value', () => {
      expect(toggleHas('', 'commands')).toBe('commands')
    })

    it('removes a token that is present', () => {
      expect(toggleHas('commands', 'commands')).toBe('')
    })

    it('returns to the start after toggling the same token twice', () => {
      expect(toggleHas(toggleHas('', 'tcpip'), 'tcpip')).toBe('')
    })

    it('removes only the toggled token and keeps the rest', () => {
      expect(toggleHas('success,commands,tcpip', 'commands')).toBe('success,tcpip')
    })
  })

  describe('ordering', () => {
    it('emits tokens in canonical row order, not insertion order', () => {
      expect(toggleHas('downloads', 'success')).toBe('success,downloads')
      expect(toggleHas('success', 'downloads')).toBe('success,downloads')
    })

    it('gives the same string whatever the click order', () => {
      const a = toggleHas(toggleHas('', 'tcpip'), 'success')
      const b = toggleHas(toggleHas('', 'success'), 'tcpip')
      expect(a).toBe('success,tcpip')
      expect(b).toBe('success,tcpip')
    })
  })

  describe('duplicates', () => {
    it('collapses a duplicated input token when adding another', () => {
      expect(toggleHas('commands,commands', 'tcpip')).toBe('commands,tcpip')
    })

    it('removes every copy of a duplicated token when toggling it off', () => {
      expect(toggleHas('commands,commands', 'commands')).toBe('')
    })
  })

  describe('whitespace', () => {
    it('trims spaces around tokens so they are kept', () => {
      expect(toggleHas('success, commands', 'tcpip')).toBe('success,commands,tcpip')
    })

    it('matches a spaced token when toggling it off', () => {
      expect(toggleHas('success, commands', 'commands')).toBe('success')
    })
  })

  describe('unknown tokens', () => {
    it('drops an unknown token already in the value', () => {
      expect(toggleHas('success,bogus', 'commands')).toBe('success,commands')
    })

    it('leaves the value unchanged when the toggled token is unknown', () => {
      expect(toggleHas('success', 'bogus')).toBe('success')
      expect(toggleHas('commands', '')).toBe('commands')
    })
  })

  describe('empty input', () => {
    it('returns an empty value for an empty value and empty token', () => {
      expect(toggleHas('', '')).toBe('')
    })
  })

  describe('none', () => {
    it('selects none on its own when the value is empty', () => {
      expect(toggleHas('', 'none')).toBe('none')
    })

    it('replaces every other selection with none', () => {
      expect(toggleHas('success,commands', 'none')).toBe('none')
    })

    it('clears none when toggled while selected', () => {
      expect(toggleHas('none', 'none')).toBe('')
    })

    it('clears none even when it is duplicated', () => {
      expect(toggleHas('none,none', 'none')).toBe('')
    })

    it('drops none when a real token is added', () => {
      expect(toggleHas('none', 'tcpip')).toBe('tcpip')
    })

    it('keeps none when an unknown token is toggled', () => {
      expect(toggleHas('none', 'bogus')).toBe('none')
    })
  })
})
