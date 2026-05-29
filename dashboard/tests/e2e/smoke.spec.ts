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
    await expect(
      page.getByRole('heading', { level: 1, name: 'Route not found' }),
    ).toBeVisible()
    await expectAxeClean(page)
  })
})
