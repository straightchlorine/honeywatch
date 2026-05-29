import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => import('../views/OverviewView.vue'),
    meta: { title: 'Overview' },
  },
  // Sessions (list + detail), Credentials, and IP views are deferred until
  // their data/UX is ready (see docs/frontend-foundation-plan.md). The
  // /api/v1/sessions endpoints remain; the reusable base/Pagination control is
  // kept ready for the list view's return. Unknown paths fall through below.
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
