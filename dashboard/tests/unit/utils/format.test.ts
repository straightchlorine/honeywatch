import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fmtDelta, fmtNumber, fmtRelativeTime } from '@/utils/format'

describe('fmtNumber', () => {
  it('formats integers with thousands separators', () => {
    expect(fmtNumber(1234567)).toBe('1,234,567')
  })

  it('formats zero', () => {
    expect(fmtNumber(0)).toBe('0')
  })

  it('formats small numbers without separators', () => {
    expect(fmtNumber(42)).toBe('42')
  })
})

describe('fmtDelta', () => {
  it('formats a positive delta with percentage', () => {
    expect(fmtDelta({ delta: 100, pct_change: 12.5 })).toBe('+100 (+12.5%)')
  })

  it('formats a negative delta with percentage', () => {
    expect(fmtDelta({ delta: -50, pct_change: -5.25 })).toBe('-50 (-5.3%)')
  })

  it('formats a zero delta with percentage', () => {
    expect(fmtDelta({ delta: 0, pct_change: 0 })).toBe('0 (0.0%)')
  })

  it('omits the percentage when pct_change is null (positive delta)', () => {
    expect(fmtDelta({ delta: 7, pct_change: null })).toBe('+7')
  })

  it('omits the percentage when pct_change is null (negative delta)', () => {
    expect(fmtDelta({ delta: -3, pct_change: null })).toBe('-3')
  })

  it('omits the percentage when pct_change is null (zero delta)', () => {
    expect(fmtDelta({ delta: 0, pct_change: null })).toBe('0')
  })

  it('uses thousands separators in the absolute delta', () => {
    expect(fmtDelta({ delta: 12345, pct_change: 10 })).toBe('+12,345 (+10.0%)')
  })
})

describe('fmtRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-28T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const ago = (ms: number) => new Date(Date.now() - ms).toISOString()

  it('reports seconds for sub-minute deltas', () => {
    expect(fmtRelativeTime(ago(3_000))).toBe('3s ago')
  })

  it('reports seconds at the 59s boundary', () => {
    expect(fmtRelativeTime(ago(59_000))).toBe('59s ago')
  })

  it('crosses into minutes at 60s', () => {
    expect(fmtRelativeTime(ago(60_000))).toBe('1m ago')
  })

  it('reports minutes at the 59m boundary', () => {
    expect(fmtRelativeTime(ago(59 * 60_000))).toBe('59m ago')
  })

  it('crosses into hours at 60m', () => {
    expect(fmtRelativeTime(ago(60 * 60_000))).toBe('1h ago')
  })

  it('reports hours at the 23h boundary', () => {
    expect(fmtRelativeTime(ago(23 * 60 * 60_000))).toBe('23h ago')
  })

  it('crosses into days at 24h', () => {
    expect(fmtRelativeTime(ago(24 * 60 * 60_000))).toBe('1d ago')
  })

  it('reports multi-day deltas', () => {
    expect(fmtRelativeTime(ago(5 * 24 * 60 * 60_000))).toBe('5d ago')
  })
})
