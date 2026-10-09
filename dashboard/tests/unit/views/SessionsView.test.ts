import { defineComponent, h, Suspense } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { newTestQueryClient } from '../../helpers/mount'

const PAGES = 3
const PER = 3
const { listFn } = vi.hoisted(() => ({ listFn: vi.fn() }))

vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  listSessionsOptions: (o: { query: Record<string, unknown> }) => ({
    queryKey: ['sessions', o.query],
    queryFn: () => listFn(o.query),
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
    items: Array.from({ length: PER }, (_, i) => ({
      id: `${sort}-p${page}-r${i}`,
      protocol: 'ssh',
      country_code: 'US',
      country: 'United States',
      city: null,
      started_at: '2026-05-28T12:34:00Z',
      ended_at: '2026-05-28T12:40:00Z',
      n_commands: 1,
      n_downloads: 0,
      n_tcpip: 0,
      auth_success: true,
      interest: 10,
    })),
    max_interest: 20,
    meta: { total: PAGES * PER, pages: PAGES, page, per_page: PER },
  }
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/sessions', component: { template: '<div />' } }],
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
