import { describe, expect, it } from 'vitest'
import { sanitizeAttackerText } from '@/utils/sanitize'

describe('sanitizeAttackerText (escape mode)', () => {
  it('passes through ordinary text unchanged', () => {
    expect(sanitizeAttackerText('hello world 123')).toBe('hello world 123')
  })

  it('preserves tab/newline/CR by default', () => {
    expect(sanitizeAttackerText('a\tb\nc\rd')).toBe('a\tb\nc\rd')
  })

  it('escapes C0 control chars (except whitespace) as \\xHH', () => {
    // 0x07 BEL
    expect(sanitizeAttackerText('a\x07b')).toBe('a\\x07b')
  })

  it('escapes DEL and C1 controls', () => {
    expect(sanitizeAttackerText('\x7f\x9f')).toBe('\\x7F\\x9F')
  })

  it('escapes bidi overrides and isolates', () => {
    const bidi = String.fromCharCode(0x202e, 0x2066) // RLO + LRI
    expect(sanitizeAttackerText(bidi)).toBe('\\x202E\\x2066')
  })

  it('escapes LRM/RLM bidi marks', () => {
    const marks = String.fromCharCode(0x200e, 0x200f)
    expect(sanitizeAttackerText(marks)).toBe('\\x200E\\x200F')
  })
})

describe('sanitizeAttackerText (strip mode)', () => {
  it('removes dangerous code points entirely', () => {
    const raw = 'a' + String.fromCharCode(0x07, 0x202e) + 'b'
    expect(sanitizeAttackerText(raw, { mode: 'strip' })).toBe('ab')
  })

  it('with allowWhitespace=false also strips tab/newline/CR', () => {
    expect(
      sanitizeAttackerText('a\tb\nc', { mode: 'strip', allowWhitespace: false }),
    ).toBe('abc')
  })
})

describe('sanitizeAttackerText (byte cap)', () => {
  it('truncates raw input to maxBytes before scanning and appends a marker', () => {
    const out = sanitizeAttackerText('x'.repeat(100), { maxBytes: 10 })
    expect(out).toBe('x'.repeat(10) + '\n... [truncated]')
  })

  it('does not truncate when under the cap', () => {
    expect(sanitizeAttackerText('short', { maxBytes: 1024 })).toBe('short')
  })

  it('measures bytes, not code units, for multi-byte input', () => {
    // '€' is 3 UTF-8 bytes; cap of 3 keeps exactly one, decoder drops partials.
    const out = sanitizeAttackerText('€€€', { maxBytes: 4 })
    expect(out.endsWith('... [truncated]')).toBe(true)
    expect(out.startsWith('€')).toBe(true)
  })
})
