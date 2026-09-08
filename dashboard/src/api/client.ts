/**
 * OpenAPI client with dev-mode error logging; always import from here so all requests route through the interceptor.
 */
import { client } from './generated/client.gen'

client.interceptors.response.use(async (response) => {
  if (!response.ok && import.meta.env.DEV) {
    const url = response.url.split('?')[0]
    console.error('[api]', response.status, url)
  }
  return response
})

export { client }
