import { defineComponent, h, Suspense } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { newTestQueryClient } from '../../helpers/mount'
import { setLastViewed, setViewedSpot, takeLastViewed } from '@/utils/lastViewed'
import type { SessionSummaryResponse } from '@/api/generated/types.gen'

const PAGES = 3
const PER = 3
const { listFn, runFn } = vi.hoisted(() => ({ listFn: vi.fn(), runFn: vi.fn() }))

vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  listSessionsOptions: (o: { query: Record<string, unknown> }) => ({
    queryKey: ['sessions', o.query],
    queryFn: () => listFn(o.query),
  }),
  listRunSessionsOptions: (o: { query: Record<string, unknown> }) => ({
    queryKey: ['run', o.query],
    queryFn: () => runFn(o.query),
  }),
  statsOutcomesOptions: (o: unknown) => ({ queryKey: ['outcomes', o], queryFn: async () => ({}) }),
}))
vi.mock('@/composables/useCountryOptions', async () => {
  const { computed } = await import('vue')
  return { useCountryOptions: () => computed(() => [{ value: '', label: 'All countries' }]) }
})

import SessionsView from '@/views/SessionsView.vue'

function listPage(q: Record<string, unknown>) {
  const page = Number(q.page ?? 1)
  const sort = String(q.sort ?? 'interest')
  return {
    items: Array.from({ length: PER }, (_, i): SessionSummaryResponse => ({
      id: `${sort}-p${page}-r${i}`,
      protocol: 'ssh',
      country_code: 'US',
      country: 'United States',
      city: null,
      asn_org: null,
      client_version: null,
      lat: null,
      lon: null,
      src_port: 40000 + i,
      dst_port: 22,
      started_at: '2026-05-28T12:34:00Z',
      ended_at: '2026-05-28T12:40:00Z',
      n_commands: 1,
      command_count: 1,
      n_downloads: 0,
      n_tcpip: 0,
      auth_success: true,
      has_successful_login: true,
      auth_attempt_count: 1,
      category: 'active',
      // Distinct per row: identical neighbours would collapse into a group row.
      interest: 10 + i,
    })),
    max_interest: 20,
    meta: { total: PAGES * PER, pages: PAGES, page, per_page: PER },
  }
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/sessions', name: 'sessions', component: { template: '<div />' } },
    { path: '/sessions/:id', name: 'session-detail', component: { template: '<div />' } },
    { path: '/pulse', name: 'pulse', component: { template: '<div />' } },
  ],
})

let wrapper: VueWrapper | undefined
async function mountAt(query: Record<string, string> = {}) {
  await router.replace({ path: '/sessions', query })
  const Wrapper = defineComponent({
    render: () => h(Suspense, null, { default: () => h(SessionsView) }),
  })
  wrapper = mount(Wrapper, {
    attachTo: document.body,
    global: {
      plugins: [router, [VueQueryPlugin, { queryClient: newTestQueryClient() }]],
      stubs: {
        PageShell: { template: '<div><slot name="head" /><slot /></div>' },
        TopBar: true,
        SessionExpansion: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

const rowEls = () => [...document.querySelectorAll<HTMLElement>('tr.srow')]
async function press(el: Element, key: string) {
  el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  await flushPromises()
}

beforeEach(() => {
  listFn.mockReset()
  listFn.mockImplementation(async (q) => listPage(q))
  runFn.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('SessionsView keyboard grid', () => {
  it('moves focus with Arrow/Home/End and keeps exactly one row tabbable', async () => {
    await mountAt()
    const rows = rowEls()
    rows[0]!.focus()
    await press(rows[0]!, 'ArrowDown')
    expect(document.activeElement).toBe(rows[1])
    await press(rows[1]!, 'End')
    expect(document.activeElement).toBe(rows[PER - 1])
    await press(rows[PER - 1]!, 'Home')
    expect(document.activeElement).toBe(rows[0])
    await press(rows[0]!, 'ArrowDown')
    await press(rows[1]!, 'ArrowUp')
    expect(document.activeElement).toBe(rows[0])

    rows[2]!.focus()
    await flushPromises()
    const tabbable = rowEls().filter((r) => r.getAttribute('tabindex') === '0')
    expect(tabbable).toEqual([rows[2]])
  })

  it('clamps ArrowUp at the top and ArrowDown at the bottom', async () => {
    await mountAt()
    const rows = rowEls()
    rows[0]!.focus()
    await press(rows[0]!, 'ArrowUp')
    expect(document.activeElement).toBe(rows[0])
    rows[PER - 1]!.focus()
    await press(rows[PER - 1]!, 'ArrowDown')
    expect(document.activeElement).toBe(rows[PER - 1])
  })

  it('PageDown goes to the next page and focuses its first row once it has loaded', async () => {
    await mountAt()
    const rows = rowEls()
    rows[1]!.focus()
    await press(rows[1]!, 'PageDown')
    expect(router.currentRoute.value.query.page).toBe('2')
    expect(document.activeElement).toBe(rowEls()[0])
    expect(rowEls()[0]!.dataset.id).toBe('interest-p2-r0')
  })

  it('PageDown on the last page neither advances nor arms a focus grab for later refetches', async () => {
    await mountAt({ page: String(PAGES) })
    const rows = rowEls()
    rows[1]!.focus()
    await press(rows[1]!, 'PageDown')
    expect(router.currentRoute.value.query.page).toBe(String(PAGES))
    expect(listFn.mock.calls.every(([q]) => q.page <= PAGES)).toBe(true)

    // A later refetch (sort change) must leave focus alone rather than jump to row 1.
    await router.replace({ path: '/sessions', query: { sort: 'recent' } })
    await flushPromises()
    expect(rowEls()[0]!.dataset.id).toBe('recent-p1-r0')
    expect(document.activeElement).not.toBe(rowEls()[0])
  })
})

describe('SessionsView page box', () => {
  it('resets non-numeric input to the current page and clamps oversized input', async () => {
    const w = await mountAt({ page: '2' })
    const input = w.get<HTMLInputElement>('#page-input')

    input.element.value = 'abc'
    await input.trigger('change')
    await flushPromises()
    expect(input.element.value).toBe('2')
    expect(router.currentRoute.value.query.page).toBe('2')

    input.element.value = '999'
    await input.trigger('change')
    await flushPromises()
    expect(input.element.value).toBe(String(PAGES))
    expect(router.currentRoute.value.query.page).toBe(String(PAGES))
  })

  it('announces the new page once it has loaded', async () => {
    const w = await mountAt()
    await w.get('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    expect(w.get('[role="status"][aria-live="polite"]').text()).toBe(
      `Page 2 of ${PAGES}, ${PER} sessions`,
    )
  })

  it('keeps Next focusable and ignores clicks while the next page loads', async () => {
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => (release = resolve))
    listFn.mockImplementation(async (q) => {
      if (q.page === 2) await gate
      return listPage(q)
    })
    const w = await mountAt()
    const next = () => w.get('button[aria-label="Next page"]')
    await next().trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.page).toBe('2')
    expect(next().attributes('disabled')).toBeUndefined()
    expect(next().attributes('aria-disabled')).toBe('true')

    await next().trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.page).toBe('2')

    release()
    await flushPromises()
    expect(next().attributes('aria-disabled')).toBe('false')
  })
})

describe('SessionsView end-of-page line', () => {
  it('counts rows and leaves paging to the pager', async () => {
    const w = await mountAt()
    expect(w.get('.page-end').text()).toContain(`${PER} rows shown`)
    expect(w.get('.page-end').find('button').exists()).toBe(false)
  })
})

describe('SessionsView search box', () => {
  it('shows a ?q= that changes under the box, such as on Back', async () => {
    await mountAt()
    await router.replace({ path: '/sessions', query: { q: 'abc' } })
    await flushPromises()
    expect(document.querySelector<HTMLInputElement>('#session-search')!.value).toBe('abc')
  })
})

describe('SessionsView load errors', () => {
  it('shows a Retry block when a refetch fails', async () => {
    const w = await mountAt()
    listFn.mockRejectedValue(new Error('boom'))
    await router.replace({ path: '/sessions', query: { sort: 'recent' } })
    await flushPromises()

    const err = w.get('.load-error')
    expect(err.attributes('role')).toBe('alert')
    expect(err.text()).toContain('Retry')
  })
})

describe('SessionsView score explanation', () => {
  it('puts the interest score explanation in the Session column header for keyboard users', async () => {
    await mountAt()
    const btn = document.querySelector('th button')!
    expect(btn.getAttribute('title')).toContain(
      'Interest score - higher when a session ran commands',
    )
  })
})

describe('SessionsView look-alike runs', () => {
  const RUN = 45
  const AS_OF = '2026-05-28T12:45:00+00:00'
  const run = {
    count: RUN,
    offset: 1,
    countries: 1,
    country_code: 'US',
    country: 'United States',
    min_duration_s: 4,
    max_duration_s: 58,
    oldest: '2026-05-28T12:00:00Z',
    newest: '2026-05-28T12:30:00Z',
  }
  const member = (i: number) => ({ ...listPage({}).items[0]!, id: `same-${i}` })
  const folded = () => {
    const page = listPage({})
    return { ...page, as_of: AS_OF, items: [{ ...page.items[0]!, run }, ...page.items.slice(1)] }
  }
  const groupEl = () => document.querySelector<HTMLElement>('tr.sgroup')
  const moreBtn = () => document.querySelector<HTMLElement>('tr.run-more button')
  const clickRow = async (el: Element | null) => {
    el!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
  }

  beforeEach(() => {
    listFn.mockImplementation(async () => folded())
    runFn.mockImplementation(async (q: { page: number; per_page: number; count: number }) => {
      const from = (q.page - 1) * q.per_page
      const n = Math.min(q.per_page, q.count - from)
      return {
        items: Array.from({ length: n }, (_, i) => member(from + i)),
        meta: { page: q.page, per_page: q.per_page, pages: 2, total: q.count },
      }
    })
  })

  it('asks the API to fold, and shows the run behind its first row with the count', async () => {
    const w = await mountAt()
    expect(listFn.mock.calls[0]![0]).toMatchObject({ fold: true })
    expect(rowEls().map((r) => r.dataset.id)).toEqual(listPage({}).items.map((r) => r.id))
    expect(groupEl()!.textContent).toContain(`${RUN} more like this`)
    expect(groupEl()!.getAttribute('aria-expanded')).toBe('false')
    expect(runFn).not.toHaveBeenCalled()
    expect(w.get('.page-end').text()).toContain(`${PER} rows shown`)
    expect(w.get('.page-end').text()).toContain(`${RUN} similar sessions folded into 1 group`)
  })

  it('fetches the run from the list snapshot when opened, and folds it again', async () => {
    const w = await mountAt({ sort: 'recent', country: 'US' })
    await clickRow(groupEl())
    expect(runFn.mock.calls[0]![0]).toMatchObject({
      as_of: AS_OF,
      offset: 1,
      count: RUN,
      page: 1,
      sort: 'recent',
      country: 'US',
    })
    expect(runFn.mock.calls[0]![0]).not.toHaveProperty('fold')
    expect(document.querySelectorAll('tr.srow.nested')).toHaveLength(40)
    expect(groupEl()!.getAttribute('aria-expanded')).toBe('true')
    expect(groupEl()!.textContent).toContain('Hide')
    expect(w.get('.page-end').text()).toContain(`${PER + 40} rows shown`)

    await clickRow(groupEl())
    expect(document.querySelectorAll('tr.srow.nested')).toHaveLength(0)
  })

  it('loads the rest of a long run on demand', async () => {
    await mountAt()
    await clickRow(groupEl())
    expect(moreBtn()!.textContent!.trim()).toBe('Show 5 more')
    moreBtn()!.click()
    await flushPromises()
    expect(runFn.mock.calls.at(-1)![0]).toMatchObject({ page: 2 })
    expect(document.querySelectorAll('tr.srow.nested')).toHaveLength(RUN)
    expect(moreBtn()).toBeNull()
  })

  it('says so when a run page fails, and loads that page again on Retry', async () => {
    runFn.mockRejectedValueOnce(new Error('boom'))
    await mountAt()
    await clickRow(groupEl())
    const more = () => document.querySelector<HTMLElement>('tr.run-more')!
    expect(more().querySelector('[role="alert"]')!.textContent).toContain(
      'Could not load these sessions',
    )
    expect(more().textContent).not.toContain('Show')
    expect(document.querySelectorAll('tr.srow.nested')).toHaveLength(0)

    const retry = [...more().querySelectorAll('button')].find(
      (b) => b.textContent?.trim() === 'Retry',
    )!
    retry.click()
    await flushPromises()
    expect(runFn).toHaveBeenCalledTimes(2)
    expect(more().querySelector('[role="alert"]')).toBeNull()
    expect(document.querySelectorAll('tr.srow.nested')).toHaveLength(RUN - 5)
  })

  it('keeps run requests on the list the rows came from while a new sort loads', async () => {
    await mountAt()
    await clickRow(groupEl())
    runFn.mockClear()
    let release: () => void = () => {}
    const gate = new Promise<void>((resolve) => (release = resolve))
    listFn.mockImplementation(async (q) => {
      if (q.sort === 'recent') await gate
      return folded()
    })
    await router.replace({ path: '/sessions', query: { sort: 'recent' } })
    await flushPromises()
    expect(runFn).not.toHaveBeenCalled()

    release()
    await flushPromises()
    expect(runFn).toHaveBeenCalled()
    expect(runFn.mock.calls.every(([q]) => q.sort === 'recent' && q.as_of === AS_OF)).toBe(true)
  })

  it('closes an expanded member when its run folds away', async () => {
    await mountAt()
    await clickRow(groupEl())
    await clickRow(document.querySelector('tr.srow[data-id="same-2"]'))
    expect(router.currentRoute.value.query.open).toBe('same-2')
    await clickRow(groupEl())
    expect(router.currentRoute.value.query.open).toBeUndefined()
    expect(router.currentRoute.value.query.run).toBeUndefined()
  })

  it('reopens the run holding the expanded ?open= session on reload', async () => {
    await mountAt()
    await clickRow(groupEl())
    await clickRow(document.querySelector('tr.srow[data-id="same-2"]'))
    const query = { ...router.currentRoute.value.query } as Record<string, string>
    expect(query).toMatchObject({ open: 'same-2', run: listPage({}).items[0]!.id })
    wrapper?.unmount()

    await mountAt(query)
    expect(groupEl()!.getAttribute('aria-expanded')).toBe('true')
    const opened = document.querySelector('tr.srow[data-id="same-2"]')
    expect(opened!.getAttribute('aria-expanded')).toBe('true')

    await clickRow(opened)
    expect(router.currentRoute.value.query.run).toBeUndefined()
  })
})

describe('SessionsView expanding rows', () => {
  const rowEl = (i: number) => rowEls()[i]!

  it('toggles against the requested ?open=, so two taps in one tick leave the row closed', async () => {
    await mountAt()
    const row = rowEl(0)
    row.click()
    row.click()
    await flushPromises()
    expect(router.currentRoute.value.query.open).toBeUndefined()
    expect(row.getAttribute('aria-expanded')).toBe('false')
  })

  it('opens only the last of two quick taps on different rows', async () => {
    await mountAt()
    rowEl(0).click()
    rowEl(1).click()
    await flushPromises()
    expect(router.currentRoute.value.query.open).toBe(rowEl(1).dataset.id)
    expect(document.querySelectorAll('tr.srow[aria-expanded="true"]')).toHaveLength(1)
  })

  it('scrolls the table back by however far the tapped row moved when a panel above it collapsed', async () => {
    await mountAt({ open: 'interest-p1-r0' })
    const tapped = rowEl(2)
    let top = 300
    tapped.getBoundingClientRect = () => ({ top }) as DOMRect
    const scroller = document.querySelector<HTMLElement>('.tbl-scroll')!
    Object.defineProperty(scroller, 'scrollHeight', { value: 900, configurable: true })
    Object.defineProperty(scroller, 'clientHeight', { value: 500, configurable: true })
    scroller.scrollTop = 120
    tapped.addEventListener('click', () => (top = 204), { once: true })
    tapped.click()
    await flushPromises()
    expect(scroller.scrollTop).toBe(120 - 96)
  })
})

describe('SessionsView while leaving for a session', () => {
  it('freezes its query and does not refetch when another page is opened', async () => {
    await mountAt({ sort: 'recent' })
    const calls = listFn.mock.calls.length
    await router.push('/pulse')
    await flushPromises()
    expect(listFn).toHaveBeenCalledTimes(calls)
    expect(router.currentRoute.value.query).toEqual({})
  })

  it('neither refetches nor rewrites the detail route from a trailing search write', async () => {
    await mountAt({ sort: 'recent' })
    const calls = listFn.mock.calls.length
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      const input = document.querySelector<HTMLInputElement>('#session-search')!
      input.value = 'abc'
      input.dispatchEvent(new Event('input', { bubbles: true }))
      await router.push('/sessions/abc123')
      await vi.advanceTimersByTimeAsync(1000)
    } finally {
      vi.useRealTimers()
    }
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/sessions/abc123')
    expect(router.currentRoute.value.query).toEqual({})
    expect(listFn).toHaveBeenCalledTimes(calls)
  })
})

describe('SessionsView on a phone', () => {
  let change: (matches: boolean) => void = () => {}
  const lead = (i: number, id: string) => ({
    ...listPage({}).items[i]!,
    id,
    run: {
      count: 2,
      offset: i + 1,
      countries: 1,
      country_code: 'US',
      country: 'United States',
      min_duration_s: 4,
      max_duration_s: 58,
      oldest: '2026-05-28T12:00:00Z',
      newest: '2026-05-28T12:30:00Z',
    },
  })
  const heads = () => [...document.querySelectorAll<HTMLElement>('.run-head')]
  const tap = async (el: Element) => {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    await flushPromises()
  }

  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      matches: true,
      addEventListener: (_: string, fn: (e: { matches: boolean }) => void) => {
        change = (matches) => fn({ matches })
      },
      removeEventListener: () => {},
    }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders the list of link rows, not the table, with the short sort clause', async () => {
    await mountAt({ sort: 'recent' })
    expect(document.querySelector('table')).toBeNull()
    expect(document.querySelectorAll('ul.sessions-phone a.row')).toHaveLength(PER)
    expect(document.querySelector('.sub')!.textContent).toContain('newest first')
  })

  it('keeps ?run= as comma-separated ids, one entry per open run, and reopens them from it', async () => {
    listFn.mockImplementation(async () => ({
      ...listPage({}),
      as_of: '2026-05-28T12:45:00+00:00',
      items: [lead(0, 'aaa111'), lead(1, 'bbb222'), listPage({}).items[2]!],
    }))
    runFn.mockImplementation(async (q: { count: number }) => ({
      items: Array.from({ length: q.count }, (_, i) => ({
        ...listPage({}).items[0]!,
        id: `m-${i}`,
      })),
      meta: { page: 1, per_page: 40, pages: 1, total: q.count },
    }))
    await mountAt()
    await tap(heads()[0]!)
    expect(router.currentRoute.value.query.run).toBe('aaa111')
    await tap(heads()[1]!)
    expect(router.currentRoute.value.query.run).toBe('aaa111,bbb222')
    await tap(heads()[0]!)
    expect(router.currentRoute.value.query.run).toBe('bbb222')
    await tap(heads()[1]!)
    expect(router.currentRoute.value.query.run).toBeUndefined()

    wrapper?.unmount()
    await mountAt({ run: 'aaa111,bbb222' })
    expect(heads().map((h) => h.getAttribute('aria-expanded'))).toEqual(['true', 'true'])
    expect(document.querySelectorAll('a.row.child')).toHaveLength(4)
  })

  it('never expands a row, so ?open= and a lone sha256 match leave the URL alone', async () => {
    const sha = 'a'.repeat(64)
    listFn.mockImplementation(async () => ({
      ...listPage({}),
      items: listPage({}).items.slice(0, 1),
    }))
    await mountAt({ sha256: sha, open: 'interest-p1-r0' })
    expect(document.querySelector('tr.expand')).toBeNull()
    expect(document.querySelector('[aria-expanded="true"]')).toBeNull()
    wrapper?.unmount()
    await mountAt({ sha256: sha })
    expect(router.currentRoute.value.query.open).toBeUndefined()
  })

  it('remembers the tapped session for Back and goes to its page', async () => {
    await mountAt()
    await tap(document.querySelector('a.row')!)
    expect(router.currentRoute.value.name).toBe('session-detail')
    expect(takeLastViewed()).toBe('interest-p1-r0')
    await router.replace('/sessions')
  })

  describe('coming back', () => {
    const runLead = () => ({
      ...listPage({}),
      as_of: '2026-05-28T12:45:00+00:00',
      items: [lead(0, 'aaa111'), ...listPage({}).items.slice(1)],
    })
    const focusedId = () => (document.activeElement as HTMLElement | null)?.dataset.id

    beforeEach(() => {
      vi.spyOn(window, 'scrollBy').mockImplementation(() => {})
    })
    afterEach(() => {
      takeLastViewed()
      document.getElementById('main')?.remove()
      vi.restoreAllMocks()
    })

    it('focuses the row that was opened', async () => {
      setLastViewed('interest-p1-r1')
      await mountAt()
      expect(focusedId()).toBe('interest-p1-r1')
      expect(takeLastViewed()).toBeNull()
    })

    it('waits for the members of an open run, then focuses the member that was opened', async () => {
      listFn.mockImplementation(async () => runLead())
      runFn.mockImplementation(async (q: { count: number }) => ({
        items: Array.from({ length: q.count }, (_, i) => ({
          ...listPage({}).items[0]!,
          id: `m-${i}`,
        })),
        meta: { page: 1, per_page: 40, pages: 1, total: q.count },
      }))
      setLastViewed('m-1')
      await mountAt({ run: 'aaa111' })
      expect(focusedId()).toBe('m-1')
    })

    it('reopens each run as deep as it was, so a row from "Show more" is there to land on', async () => {
      listFn.mockImplementation(async () => ({
        ...runLead(),
        items: [{ ...lead(0, 'aaa111'), run: { ...lead(0, 'aaa111').run, count: 60 } }],
      }))
      runFn.mockImplementation(async (q: { page: number }) => ({
        items: [{ ...listPage({}).items[0]!, id: `m-p${q.page}` }],
        meta: { page: q.page, per_page: 40, pages: 2, total: 60 },
      }))
      setLastViewed('m-p2')
      setViewedSpot({ id: 'm-p2', top: 0, runs: new Map([['aaa111', 2]]) })
      await mountAt({ run: 'aaa111' })
      expect(runFn.mock.calls.map(([q]) => q.page)).toEqual([1, 2])
      expect(focusedId()).toBe('m-p2')
    })

    it('scrolls a row that is off screen into view', async () => {
      const scrollIntoView = vi.fn()
      Element.prototype.scrollIntoView = scrollIntoView
      vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
        top: -80,
        bottom: -28,
      } as DOMRect)
      setLastViewed('interest-p1-r1')
      await mountAt()
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' })
      // @ts-expect-error jsdom has none
      delete Element.prototype.scrollIntoView
    })

    it('falls back to the page when the row is not there', async () => {
      const main = document.body.appendChild(document.createElement('main'))
      main.id = 'main'
      main.tabIndex = -1
      setLastViewed('gone')
      await mountAt()
      expect(document.activeElement).toBe(main)
    })

    it('takes ?open= as a row to focus, then strips it', async () => {
      await mountAt({ open: 'interest-p1-r2' })
      expect(focusedId()).toBe('interest-p1-r2')
      expect(router.currentRoute.value.query.open).toBeUndefined()
    })

    it('does nothing when nothing was opened', async () => {
      await mountAt()
      expect(document.activeElement).toBe(document.body)
    })
  })

  it('swaps to the table across the breakpoint and keeps the filters', async () => {
    await mountAt({ sort: 'recent' })
    change(false)
    await flushPromises()
    expect(document.querySelector('ul.sessions-phone')).toBeNull()
    expect(rowEls()).toHaveLength(PER)
    expect(router.currentRoute.value.query.sort).toBe('recent')
  })
})
