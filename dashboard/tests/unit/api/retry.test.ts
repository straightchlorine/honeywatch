import { describe, expect, it } from 'vitest'
import { shouldRetry } from '@/api/retry'

describe('shouldRetry', () => {
  it('retries 5xx envelope errors until the cap', () => {
    const err = { code: 503, status: 'Service Unavailable' }
    expect(shouldRetry(0, err)).toBe(true)
    expect(shouldRetry(1, err)).toBe(true)
    expect(shouldRetry(2, err)).toBe(false) // cap reached
  })

  it('does not retry 4xx client errors', () => {
    expect(shouldRetry(0, { code: 404, status: 'Not Found' })).toBe(false)
    expect(shouldRetry(0, { code: 422, status: 'Unprocessable Entity' })).toBe(false)
  })

  it('retries network errors (no code) within the cap', () => {
    expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true)
    expect(shouldRetry(0, null)).toBe(true)
    expect(shouldRetry(2, null)).toBe(false)
  })

  it('reads the numeric code, not the string status reason phrase', () => {
    // Regression guard: the bug was reading `status` (a string) as a number.
    expect(shouldRetry(0, { code: 500, status: 'Internal Server Error' })).toBe(true)
  })
})
