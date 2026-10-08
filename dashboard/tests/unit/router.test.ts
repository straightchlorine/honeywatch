import { describe, expect, it, vi } from 'vitest'

const { exitSplash, isChunkLoadError, attemptStaleChunkReload } = vi.hoisted(() => ({
  exitSplash: vi.fn(),
  isChunkLoadError: vi.fn(),
  attemptStaleChunkReload: vi.fn(),
}))
vi.mock('@/utils/splash', () => ({ exitSplash }))
// Every page fails to load, so each navigation ends in the router's onError handler.
vi.mock('@/utils/retryImport', () => ({
  retryImport: () => Promise.reject(new Error('chunk failed')),
  isChunkLoadError,
  attemptStaleChunkReload,
}))

import router from '@/router'

describe('router error handler', () => {
  it('leaves the loading splash up while a reload to the fresh build is on its way', async () => {
    isChunkLoadError.mockReturnValue(true)
    attemptStaleChunkReload.mockReturnValue(true)
    await router.push('/pulse').catch(() => {})
    expect(exitSplash).not.toHaveBeenCalled()
  })

  it('removes the splash when no reload happens, so it does not load forever', async () => {
    isChunkLoadError.mockReturnValue(true)
    attemptStaleChunkReload.mockReturnValue(false)
    await router.push('/pulse').catch(() => {})
    expect(exitSplash).toHaveBeenCalledOnce()
  })

  it('removes the splash for any other navigation error', async () => {
    isChunkLoadError.mockReturnValue(false)
    await router.push('/pulse').catch(() => {})
    expect(exitSplash).toHaveBeenCalledOnce()
    expect(attemptStaleChunkReload).not.toHaveBeenCalled()
  })
})
