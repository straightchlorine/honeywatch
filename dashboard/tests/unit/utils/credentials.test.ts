import { describe, expect, it } from 'vitest'

import {
  buildCharsetRows,
  buildCredentialRows,
  buildLengthBars,
  buildPairBarRows,
  buildPasswordRows,
  fmtSuccessRate,
  pctWidth,
} from '@/utils/credentials'

describe('pctWidth', () => {
  it('scales against the max with a 2% floor for non-zero values', () => {
    expect(pctWidth(50, 100)).toBe('50%')
    expect(pctWidth(1, 100)).toBe('2%')
    expect(pctWidth(100, 100)).toBe('100%')
  })

  it('returns 0% for zero values or a zero max', () => {
    expect(pctWidth(0, 100)).toBe('0%')
    expect(pctWidth(5, 0)).toBe('0%')
  })
})

describe('buildCredentialRows', () => {
  it('renders pairs with a ":password" sub and attempt counts', () => {
    const rows = buildCredentialRows(
      [
        { username: 'root', password: '123456', count: 10, distinct_ips: null },
        { username: 'admin', password: 'admin', count: 5, distinct_ips: null },
      ],
      'attempts',
    )
    expect(rows[0]).toMatchObject({ label: 'root', sub: ':123456', value: 10, widthPct: '100%' })
    expect(rows[0]!.valueLabel).toBe('10')
    expect(rows[0]!.emphasis).toBe(false)
    expect(rows[0]!.title).toContain('root:123456 — 10 attempts')
    expect(rows[1]!.widthPct).toBe('50%')
  })

  it('drops the password sub when grouping by username', () => {
    const rows = buildCredentialRows(
      [{ username: 'root', password: null, count: 10, distinct_ips: null }],
      'attempts',
    )
    expect(rows[0]!.sub).toBeNull()
    expect(rows[0]!.label).toBe('root')
  })

  it('ranks by distinct IPs and emphasizes high botnet fan-out for ip_fanout', () => {
    const rows = buildCredentialRows(
      [
        { username: 'root', password: 'xc3511', count: 400, distinct_ips: 42 },
        { username: 'root', password: 'toor', count: 80, distinct_ips: 1 },
      ],
      'ip_fanout',
    )
    expect(rows[0]).toMatchObject({ value: 42, valueLabel: '42 IPs', emphasis: true })
    expect(rows[1]).toMatchObject({ value: 1, valueLabel: '1 IP', emphasis: false })
    expect(rows[0]!.title).toContain('tried by 42 IPs (400 attempts)')
  })

  it('renders an empty marker for blank usernames/passwords', () => {
    const rows = buildCredentialRows(
      [{ username: '', password: '', count: 3, distinct_ips: null }],
      'attempts',
    )
    expect(rows[0]!.label).toBe('‹empty›')
    expect(rows[0]!.sub).toBe(':‹empty›')
  })
})

describe('buildPairBarRows', () => {
  it('joins username:password and scales width', () => {
    const rows = buildPairBarRows([
      { username: 'root', password: 'toor', count: 4, distinct_ips: null },
      { username: 'admin', password: 'admin', count: 2, distinct_ips: null },
    ])
    expect(rows[0]).toMatchObject({ label: 'root:toor', count: 4, widthPct: '100%' })
    expect(rows[1]!.widthPct).toBe('50%')
  })
})

describe('buildPasswordRows', () => {
  it('maps passwords to bar rows with an empty marker and scaled width', () => {
    const rows = buildPasswordRows([
      { password: '123456', count: 10 },
      { password: '', count: 5 },
    ])
    expect(rows[0]).toMatchObject({ label: '123456', count: 10, widthPct: '100%' })
    expect(rows[1]!.label).toBe('‹empty›')
    expect(rows[1]!.widthPct).toBe('50%')
  })
})

describe('buildCharsetRows', () => {
  it('maps class keys to friendly labels, descending width', () => {
    const rows = buildCharsetRows([
      { name: 'lower', count: 6 },
      { name: 'digits', count: 3 },
    ])
    expect(rows[0]).toMatchObject({ label: 'Lowercase only', count: 6, widthPct: '100%' })
    expect(rows[1]).toMatchObject({ label: 'Digits only', widthPct: '50%' })
  })

  it('falls back to the raw key for an unknown class', () => {
    expect(buildCharsetRows([{ name: 'mystery', count: 1 }])[0]!.label).toBe('mystery')
  })
})

describe('buildLengthBars', () => {
  it('produces a dense 0..cap histogram with the tail labeled "{cap}+"', () => {
    const bars = buildLengthBars(
      [
        { length: 4, count: 1 },
        { length: 6, count: 3 },
      ],
      8,
    )
    expect(bars).toHaveLength(9) // 0..8 inclusive
    const byLen = Object.fromEntries(bars.map((b) => [b.length, b]))
    expect(byLen[6]!.heightPct).toBe('100%')
    expect(byLen[4]!.heightPct).toBe('33%')
    expect(byLen[0]!.heightPct).toBe('0%')
    expect(byLen[8]!.label).toBe('8+')
    expect(byLen[1]!.label).toBe('1')
  })
})

describe('fmtSuccessRate', () => {
  it('dashes a null rate and formats small/large rates', () => {
    expect(fmtSuccessRate(null)).toBe('—')
    expect(fmtSuccessRate(1.8)).toBe('1.80%')
    expect(fmtSuccessRate(33.33)).toBe('33.3%')
  })

  it('switches to 1 decimal place at exactly rate===10', () => {
    expect(fmtSuccessRate(10)).toBe('10.0%')
  })
})

describe('buildCredentialRows — attacker-text sanitization', () => {
  it('escapes a bidi override in a username and an embedded IP in a password', () => {
    // U+202E (RIGHT-TO-LEFT OVERRIDE) must not appear raw in any display field.
    const rows = buildCredentialRows(
      [{ username: '‮admin', password: 'http://1.2.3.4/x', count: 1, distinct_ips: null }],
      'attempts',
    )
    expect(rows[0]!.label).not.toContain('‮')
    expect(rows[0]!.label).toContain('\\x202E')
    // The IP in the password must be blotted; the scheme is preserved.
    expect(rows[0]!.sub).not.toContain('1.2.3.4')
    expect(rows[0]!.sub).toContain('‹ip›')
    // The title (which composes label + sub) also must be clean.
    expect(rows[0]!.title).not.toContain('‮')
    expect(rows[0]!.title).not.toContain('1.2.3.4')
  })

  it('escapes a C0 control character in a password', () => {
    // U+0001 (SOH) is a C0 control that must be shown as \\x01, not raw.
    const rows = buildCredentialRows(
      [{ username: 'root', password: 'pw\x01x', count: 2, distinct_ips: null }],
      'attempts',
    )
    expect(rows[0]!.sub).not.toContain('\x01')
    expect(rows[0]!.sub).toBe(':pw\\x01x')
  })
})

describe('buildPasswordRows — attacker-text sanitization', () => {
  it('escapes a bidi override in a raw password string', () => {
    const rows = buildPasswordRows([{ password: '‮hunter2', count: 1 }])
    expect(rows[0]!.label).not.toContain('‮')
    expect(rows[0]!.label).toContain('\\x202E')
    expect(rows[0]!.title).not.toContain('‮')
  })

  it('redacts an embedded IP literal in a password', () => {
    const rows = buildPasswordRows([{ password: 'http://1.2.3.4/x', count: 5 }])
    expect(rows[0]!.label).not.toContain('1.2.3.4')
    expect(rows[0]!.label).toContain('‹ip›')
  })
})
