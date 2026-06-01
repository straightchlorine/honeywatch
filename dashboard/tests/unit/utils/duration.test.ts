import { describe, expect, it } from 'vitest'

import { humanizeDuration } from '@/utils/duration'

describe('humanizeDuration', () => {
  it('formats sub-minute durations in seconds', () => {
    expect(humanizeDuration('2026-05-31T13:40:52Z', '2026-05-31T13:41:50Z')).toBe('58s')
  })

  it('formats minutes and seconds', () => {
    expect(humanizeDuration('2026-05-31T13:40:00Z', '2026-05-31T13:43:12Z')).toBe('3m 12s')
  })

  it('drops the seconds on a whole-minute duration', () => {
    expect(humanizeDuration('2026-05-31T13:40:00Z', '2026-05-31T13:43:00Z')).toBe('3m')
  })

  it('formats hours and minutes', () => {
    expect(humanizeDuration('2026-05-31T10:00:00Z', '2026-05-31T11:04:00Z')).toBe('1h 4m')
  })

  it('returns the placeholder for missing or negative ranges', () => {
    expect(humanizeDuration(null, '2026-05-31T13:41:50Z')).toBe('—')
    expect(humanizeDuration('2026-05-31T13:41:50Z', null)).toBe('—')
    expect(humanizeDuration('2026-05-31T13:41:50Z', '2026-05-31T13:40:00Z')).toBe('—')
  })
})
