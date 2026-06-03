import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => import('../views/OverviewView.vue'),
    meta: { title: 'Overview' },
  },
  {
    path: '/activity',
    name: 'activity',
    component: () => import('../views/ActivityView.vue'),
    meta: { title: 'Activity' },
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => import('../views/SessionsView.vue'),
    meta: { title: 'Sessions' },
  },
  {
    // Title stays generic (no session id) so an opaque identifier never leaks
    // into the document title / history.
    path: '/sessions/:id',
    name: 'session-detail',
    component: () => import('../views/SessionDetailView.vue'),
    meta: { title: 'Session' },
  },
  {
    path: '/credentials',
    name: 'credentials',
    component: () => import('../views/CredentialsView.vue'),
    meta: { title: 'Credentials' },
  },
  {
    path: '/countries',
    name: 'countries',
    component: () => import('../views/CountriesView.vue'),
    meta: { title: 'Countries' },
  },
  {
    path: '/commands',
    name: 'commands',
    component: () => import('../views/CommandsView.vue'),
    meta: { title: 'Commands' },
  },
  // The IP view is still deferred until its data/UX is ready
  // (see docs/frontend-foundation-plan.md). Unknown paths fall through below.
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Not found' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Keep the document title in sync per route; AppShell announces the change and
// moves focus to <main> for screen-reader / keyboard users (WCAG 4.1.3, 2.4.3).
router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  document.title = title ? `${title} · Honeywatch` : 'Honeywatch'
})

export default router
