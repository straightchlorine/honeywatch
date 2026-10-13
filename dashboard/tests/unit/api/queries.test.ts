import { describe, expect, it } from 'vitest'
import { suspenseAll } from '@/api/queries'

const q = (data: unknown, error: unknown = null) => ({
  suspense: () => Promise.resolve(),
  data: { value: data },
  error: { value: error },
})

describe('suspenseAll', () => {
  it('resolves when every query succeeded', async () => {
    await expect(suspenseAll(q([1]), q({ a: 1 }))).resolves.toBeUndefined()
  })

  it('throws the API error, not a TypeError, when a query failed with no data', async () => {
    const err = { code: 429, status: 'Too Many Requests' }
    await expect(suspenseAll(q([1]), q(undefined, err))).rejects.toBe(err)
  })

  it('does not throw when a query has stale data plus an error', async () => {
    await expect(suspenseAll(q([1], { code: 500 }))).resolves.toBeUndefined()
  })
})
