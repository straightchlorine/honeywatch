import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { retryImport, isChunkLoadError } from '@/utils/retryImport'

const GUARD_KEY = 'honeywatch:chunk-reload-at'

describe('retryImport', () => {
  let reload: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    reload = vi.fn()
    vi.stubGlobal('location', { reload })
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    sessionStorage.clear()
  })

  it('resolves after transient failures, retrying with backoff', async () => {
    const mod = { default: {} }
    const loader = vi
      .fn()
      .mockRejectedValueOnce(new Error('blip'))
      .mockRejectedValueOnce(new Error('blip'))
      .mockResolvedValueOnce(mod)

    const p = retryImport(loader)
    await vi.advanceTimersByTimeAsync(5_000)

    await expect(p).resolves.toBe(mod)
    expect(loader).toHaveBeenCalledTimes(3) // initial + 2 retries
    expect(reload).not.toHaveBeenCalled()
  })

  it('reloads once when retries are exhausted and the guard is clear', async () => {
    const loader = vi.fn().mockRejectedValue(new Error('boom'))

    void retryImport(loader) // resolves only via reload (never settles here)
    await vi.advanceTimersByTimeAsync(5_000)

    expect(loader).toHaveBeenCalledTimes(3)
    expect(reload).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem(GUARD_KEY)).toBeTruthy()
  })

  it('surfaces the error without reloading when it reloaded recently', async () => {
    sessionStorage.setItem(GUARD_KEY, String(Date.now()))
    const err = new Error('boom')
    const loader = vi.fn().mockRejectedValue(err)

    const p = retryImport(loader)
    const assertion = expect(p).rejects.toBe(err) // attach handler before advancing
    await vi.advanceTimersByTimeAsync(5_000)
    await assertion

    expect(reload).not.toHaveBeenCalled()
  })
})

describe('isChunkLoadError', () => {
  it('matches chunk-load failures and ignores unrelated errors', () => {
    expect(
      isChunkLoadError(new Error('Failed to fetch dynamically imported module: /assets/x.js')),
    ).toBe(true)
    expect(isChunkLoadError(new Error('Importing a module script failed.'))).toBe(true)
    expect(isChunkLoadError(new Error('some app logic bug'))).toBe(false)
  })
})
