import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { retryImport, isChunkLoadError, attemptStaleChunkReload } from '@/utils/retryImport'

// Route chunks load through retryImport: a transient fetch failure is retried,
// and a stale-deploy 404 triggers a guarded one-shot reload to the fresh build.
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => retryImport(() => import('../views/OverviewView.vue')),
    meta: { title: 'Overview' },
  },
  {
    path: '/activity',
    name: 'activity',
    component: () => retryImport(() => import('../views/ActivityView.vue')),
    meta: { title: 'Activity' },
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => retryImport(() => import('../views/SessionsView.vue')),
    meta: { title: 'Sessions' },
  },
  {
    // Title stays generic (no session id) so an opaque identifier never leaks
    // into the document title / history.
    path: '/sessions/:id',
    name: 'session-detail',
    component: () => retryImport(() => import('../views/SessionDetailView.vue')),
    meta: { title: 'Session' },
  },
  {
    path: '/credentials',
    name: 'credentials',
    component: () => retryImport(() => import('../views/CredentialsView.vue')),
    meta: { title: 'Credentials' },
  },
  {
    path: '/countries',
    name: 'countries',
    component: () => retryImport(() => import('../views/CountriesView.vue')),
    meta: { title: 'Countries' },
  },
  // The IP view is still deferred until its data/UX is ready
  // (see docs/frontend-foundation-plan.md). Unknown paths fall through below.
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => retryImport(() => import('@/views/NotFoundView.vue')),
    meta: { title: 'Not found' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Backstop: if a lazy route chunk fails to load past retryImport's own
// recovery, fall back to the same guarded reload (no-op if it just reloaded).
router.onError((err) => {
  if (isChunkLoadError(err)) attemptStaleChunkReload()
})

// Keep the document title in sync per route; AppShell announces the change and
// moves focus to <main> for screen-reader / keyboard users (WCAG 4.1.3, 2.4.3).
router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  document.title = title ? `${title} · Honeywatch` : 'Honeywatch'
})

export default router
