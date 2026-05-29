import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('runtime-config', () => {
  it('defaults baseUrl to "/" and spreads the incoming config', async () => {
    const { createClientConfig } = await import('@/api/runtime-config')
    const out = createClientConfig({ baseUrl: 'ignored', throwOnError: true } as never)
    expect(out.baseUrl).toBe('/')
    expect(out.throwOnError).toBe(true)
  })

  it('accepts an absolute http(s) base', async () => {
    vi.stubEnv('VITE_API_BASE', 'https://api.example.com')
    vi.resetModules()
    const { createClientConfig } = await import('@/api/runtime-config')
    expect(createClientConfig({} as never).baseUrl).toBe('https://api.example.com')
  })

  it('throws on a non-relative, non-absolute base', async () => {
    vi.stubEnv('VITE_API_BASE', 'ftp://nope')
    vi.resetModules()
    await expect(import('@/api/runtime-config')).rejects.toThrow(/Invalid VITE_API_BASE/)
  })
})
