import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { h, nextTick } from 'vue'
import { client } from '@/api/client'
import ErrorBoundary from '@/components/base/ErrorBoundary.vue'
import { mountWithProviders } from '../../helpers/mount'

// What the generated client throws for each failure shape, and what the error screen then shows.
async function thrown(fetchImpl: () => Promise<Response>): Promise<unknown> {
  try {
    await client.get({
      url: '/api/v1/stats/downloads',
      baseUrl: 'http://localhost',
      fetch: fetchImpl as typeof fetch,
      throwOnError: true,
    })
  } catch (err) {
    return err
  }
  throw new Error('request did not fail')
}

async function screenMessage(value: unknown): Promise<string> {
  const w = mountWithProviders(ErrorBoundary, {
    slots: {
      default: () =>
        h(() => {
          throw value
        }),
    },
  })
  await nextTick()
  return w.get('.boundary-message').text()
}

describe('generated client errors', () => {
  beforeEach(() => {
    // The dev-only response logger and the boundary both log; keep the output readable.
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('turns a fetch rejected with undefined into {}', async () => {
    const err = await thrown(() => Promise.reject(undefined))
    expect(err).toEqual({})
    expect(await screenMessage(err)).toBe('The data could not be loaded.')
  })

  it('turns a non-ok response with an empty body into {}', async () => {
    const err = await thrown(() => Promise.resolve(new Response('', { status: 503 })))
    expect(err).toEqual({})
    expect(await screenMessage(err)).toBe('The data could not be loaded.')
  })

  it('throws the JSON error envelope as is', async () => {
    const envelope = { code: 500, status: 'Internal Server Error', message: 'boom' }
    const err = await thrown(() =>
      Promise.resolve(
        new Response(JSON.stringify(envelope), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    expect(err).toEqual(envelope)
    expect(await screenMessage(err)).toBe('boom')
  })

  it('keeps a real network failure as its TypeError', async () => {
    const err = await thrown(() => Promise.reject(new TypeError('Failed to fetch')))
    expect(err).toBeInstanceOf(TypeError)
    expect(await screenMessage(err)).toBe('Failed to fetch')
  })
})
