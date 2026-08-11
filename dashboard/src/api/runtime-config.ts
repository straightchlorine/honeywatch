/**
 * Client base URL from VITE_API_BASE: must be "/" (same-origin) or absolute http(s) URL.
 * Empty string coalesces to "/".
 */
import type { CreateClientConfig } from './generated/client.gen'

// || not ?? so empty VITE_API_BASE= resolves to same-origin (per .env.example).
const rawBase = import.meta.env.VITE_API_BASE || '/'

if (rawBase !== '/' && !/^https?:\/\//i.test(rawBase)) {
  throw new Error(
    `Invalid VITE_API_BASE: ${JSON.stringify(rawBase)}. Must be "/" or an absolute http(s) URL.`,
  )
}

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  baseUrl: rawBase,
})
