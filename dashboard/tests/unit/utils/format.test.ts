import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fmtCompact, fmtDelta, fmtNumber, fmtRelativeTime } from '@/utils/format'

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

  it('renders an em dash for missing or non-finite values (never throws)', () => {
    expect(fmtNumber(undefined)).toBe('—')
    expect(fmtNumber(null)).toBe('—')
    expect(fmtNumber(NaN)).toBe('—')
  })
})

describe('fmtCompact', () => {
  it('leaves values below 1000 as plain separated numbers', () => {
    expect(fmtCompact(999)).toBe('999')
    expect(fmtCompact(42)).toBe('42')
    expect(fmtCompact(0)).toBe('0')
  })

  it('abbreviates thousands with one decimal', () => {
    expect(fmtCompact(16132)).toBe('16.1k')
    expect(fmtCompact(1822)).toBe('1.8k')
  })

  it('drops a trailing .0', () => {
    expect(fmtCompact(2000)).toBe('2k')
    expect(fmtCompact(1000000)).toBe('1M')
  })

  it('abbreviates millions and billions', () => {
    expect(fmtCompact(1234567)).toBe('1.2M')
    expect(fmtCompact(2500000000)).toBe('2.5B')
  })

  it('keeps the sign on negative values', () => {
    expect(fmtCompact(-16132)).toBe('-16.1k')
  })

  it('renders an em dash for missing or non-finite values', () => {
    expect(fmtCompact(undefined)).toBe('—')
    expect(fmtCompact(null)).toBe('—')
    expect(fmtCompact(NaN)).toBe('—')
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

  it('compacts a large absolute delta so it stays on one line', () => {
    expect(fmtDelta({ delta: 12345, pct_change: 10 })).toBe('+12.3k (+10.0%)')
  })

  it('compacts a runaway percentage (near-empty prior window)', () => {
    expect(fmtDelta({ delta: 16132, pct_change: 1822.8 })).toBe('+16.1k (+1.8k%)')
  })

  it('rounds mid-range percentages to whole numbers', () => {
    expect(fmtDelta({ delta: 500, pct_change: 342.7 })).toBe('+500 (+343%)')
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
