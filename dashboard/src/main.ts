import { createApp } from 'vue'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import './api/queries'
import './assets/tokens.css'
import { shouldRetry } from './api/retry'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      staleTime: 30_000,
      // Explicit: cached queries are dropped 5 min after the last observer
      // unmounts. Stated so the Suspense + low-gcTime footgun stays visible.
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
    },
  },
})

const app = createApp(App)
app.use(router)
app.use(VueQueryPlugin, { queryClient })
app.mount('#app')
