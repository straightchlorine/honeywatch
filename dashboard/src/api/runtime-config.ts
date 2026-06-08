import type { CreateClientConfig } from './generated/client.gen'

// `|| '/'` (not `??`) so an explicitly empty VITE_API_BASE= also resolves to
// same-origin, matching the documented behaviour in dashboard/.env.example.
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
