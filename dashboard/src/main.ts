/**
 * Query client defaults: retry transient errors only, poll instead of refetching on window focus.
 */
import { createApp } from 'vue'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import './api/queries'
// Self-hosted variable fonts (never a Google Fonts CDN - CSP stays self-only).
// Must load before tokens.css so var(--font-display)/var(--font-mono) resolve
// to the actual font faces on first paint.
import '@fontsource-variable/bricolage-grotesque/index.css'
import '@fontsource-variable/jetbrains-mono/index.css'
import './assets/tokens.css'
import { shouldRetry } from './api/retry'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      staleTime: 30_000,
      // Low gcTime can trigger Suspense bugs.
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
    },
  },
})

const app = createApp(App)
app.use(router)
app.use(VueQueryPlugin, { queryClient })
app.mount('#app')
