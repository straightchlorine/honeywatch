import { client } from './generated/client.gen'

client.interceptors.response.use(async (response) => {
  if (!response.ok) {
    console.error('[api]', response.status, response.url)
  }
  return response
})

export { client }
