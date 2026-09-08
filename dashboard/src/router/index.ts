/**
 * Vue Router configuration: routes, lazy loading (retryImport), and SEO metadata.
 * All routes lazy-load their components via retryImport to survive transient
 * chunk-fetch failures and stale deploys (guarded reload). SEO metadata (title,
 * description) is sourced from routes.json (shared with prerender script).
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { retryImport, isChunkLoadError, attemptStaleChunkReload } from '@/utils/retryImport'
import { applyRouteHead, SITE_URL } from '@/seo/head'
import seoRoutes from '@/seo/routes.json'

// Per-route SEO copy (title / <title> / description) lives in routes.json so
// the build-time prerender and sitemap generator (scripts/prerender-seo.mjs)
// share one source with the running app.
const seoByPath = new Map(seoRoutes.map((r) => [r.path, r]))
function seoMeta(path: string) {
  const r = seoByPath.get(path)
  // routes.json covers every indexable route; missing means a code/data drift.
  return { title: r?.title, seoTitle: r?.seoTitle, description: r?.description }
}

// Route chunks load through retryImport: a transient fetch failure is retried,
// and a stale-deploy 404 triggers a guarded one-shot reload to the fresh build.
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => retryImport(() => import('../views/OverviewView.vue')),
    // Owns its own PageShell/TopBar - see App.vue for the migration shim.
    meta: { ...seoMeta('/'), newShell: true },
  },
  { path: '/activity', redirect: '/pulse' },
  {
    path: '/pulse',
    name: 'pulse',
    component: () => retryImport(() => import('../views/PulseView.vue')),
    meta: { ...seoMeta('/pulse'), newShell: true },
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => retryImport(() => import('../views/SessionsView.vue')),
    meta: { ...seoMeta('/sessions'), newShell: true },
  },
  {
    // Title stays generic (no session id) so an opaque identifier never leaks
    // into the document title / history. Not in the sitemap (per-session URLs
    // are thin and unbounded), so it is left to render client-side only.
    path: '/sessions/:id',
    name: 'session-detail',
    component: () => retryImport(() => import('../views/SessionDetailView.vue')),
    meta: {
      title: 'Session',
      seoTitle: 'Session - Honeywatch',
      description: 'One recorded attacker session on the honeypot, replayed command by command.',
      newShell: true,
    },
  },
  {
    path: '/credentials',
    name: 'credentials',
    component: () => retryImport(() => import('../views/CredentialsView.vue')),
    meta: { ...seoMeta('/credentials'), newShell: true },
  },
  { path: '/countries', redirect: '/origins' },
  {
    path: '/origins',
    name: 'origins',
    component: () => retryImport(() => import('../views/OriginsView.vue')),
    meta: { ...seoMeta('/origins'), newShell: true },
  },
  {
    path: '/payloads',
    name: 'payloads',
    component: () => retryImport(() => import('../views/PayloadsView.vue')),
    meta: { ...seoMeta('/payloads'), newShell: true },
  },
  // Dev-only kit component demo; not shipped to production.
  ...(import.meta.env.DEV
    ? [
        {
          path: '/_kit',
          name: 'kit',
          component: () => retryImport(() => import('../views/KitView.vue')),
          meta: { title: 'Kit', seoTitle: 'Kit - Honeywatch', description: '', noindex: true },
        },
      ]
    : []),
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => retryImport(() => import('@/views/NotFoundView.vue')),
    meta: {
      title: 'Not found',
      seoTitle: 'Page not found - Honeywatch',
      description: '',
      noindex: true,
      newShell: true,
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { left: 0, top: 0 }
  },
})

// Backstop: if a lazy route chunk fails to load past retryImport's own
// recovery, fall back to the same guarded reload (no-op if it just reloaded).
router.onError((err) => {
  if (isChunkLoadError(err)) attemptStaleChunkReload()
})

// Keep the document head in sync per route (title, description, canonical, og).
// PageShell separately announces the change and moves focus to <main> for
// screen-reader / keyboard users (WCAG 4.1.3, 2.4.3).
router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  const seoTitle =
    (to.meta.seoTitle as string | undefined) ?? (title ? `${title} - Honeywatch` : 'Honeywatch')
  const description = (to.meta.description as string | undefined) ?? ''
  // Self-canonical per route; drop the trailing slash on sub-paths so it
  // matches the sitemap. Query/hash are excluded on purpose.
  const canonical = to.path === '/' ? `${SITE_URL}/` : `${SITE_URL}${to.path}`
  applyRouteHead({
    title: seoTitle,
    description,
    canonical,
    noindex: to.meta.noindex === true,
  })
})

export default router
