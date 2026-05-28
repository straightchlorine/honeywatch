import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import router from './router'
import './api/queries'
import './assets/tokens.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err: unknown) => {
        const status = (err as { status?: number } | null)?.status
        return count < 2 && (status === undefined || status >= 500)
      },
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(VueQueryPlugin, { queryClient })
app.mount('#app')
