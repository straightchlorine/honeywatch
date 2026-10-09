import { defineComponent, h, Suspense } from 'vue'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import type { SessionDetailResponse, SessionSummaryResponse } from '@/api/generated/types.gen'
import { listSessionsOptions } from '@/api/generated/@tanstack/vue-query.gen'
import { newTestQueryClient } from '../../helpers/mount'

// Both SessionDetailView and PageShell call useRoute(), so share one mock.
const routerBack = vi.fn()
const routerPush = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'sess-1' }, meta: {} }),
  useRouter: () => ({ back: routerBack, push: routerPush }),
}))

// Stub the query builder so top-level suspense resolves instantly with a fixed session.
vi.mock('@/api/queries', () => ({
  getSessionByIdOptions: () => ({
    queryKey: ['session', 'sess-1'],
    queryFn: async (): Promise<SessionDetailResponse> => SESSION,
  }),
}))

import SessionDetailView from '@/views/SessionDetailView.vue'

const SESSION: SessionDetailResponse = {
  id: 'sess-1',
  src_port: 51234,
  dst_port: 22,
  protocol: 'ssh',
  sensor: 'edge-01',
  country: 'United States',
  country_code: 'US',
  city: null,
  lat: null,
  lon: null,
  started_at: '2026-05-31T13:40:00Z',
  ended_at: '2026-05-31T13:42:00Z',
  auth_attempts: [],
  commands: [],
  downloads: [],
}

function setHistoryBack(back: string | null) {
  window.history.pushState(back === null ? null : { back }, '', '/sessions/sess-1')
}

// Top-level suspense requires a <Suspense> wrapper. Stubs (PageShell renders slot,
// SessionTerminal stubbed) isolate the .back button test.
async function mountView(queryClient = newTestQueryClient()) {
  const Wrapper = defineComponent({
    render: () => h(Suspense, null, { default: () => h(SessionDetailView) }),
  })
  const wrapper = mount(Wrapper, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        PageShell: { template: '<div><slot /></div>' },
        SessionTerminal: true,
        RouterLink: { props: ['to'], template: '<a :data-id="to.params.id"><slot /></a>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('SessionDetailView back navigation', () => {
  beforeEach(() => {
    routerBack.mockClear()
    routerPush.mockClear()
  })

  it('calls router.back() when the previous history entry is the sessions list', async () => {
    setHistoryBack('/sessions?sort=recent&page=3&open=abc')
    const wrapper = await mountView()

    await wrapper.get('button.back').trigger('click')

    expect(routerBack).toHaveBeenCalledTimes(1)
    expect(routerPush).not.toHaveBeenCalled()
  })

  it('falls back to push({name: "sessions"}) when there is no history state (fresh/bookmarked load)', async () => {
    setHistoryBack(null)
    const wrapper = await mountView()

    await wrapper.get('button.back').trigger('click')

    expect(routerPush).toHaveBeenCalledWith({ name: 'sessions' })
    expect(routerBack).not.toHaveBeenCalled()
  })

  it('falls back to push({name: "sessions"}) when the previous entry is another session replay', async () => {
    setHistoryBack('/sessions/xyz')
    const wrapper = await mountView()

    await wrapper.get('button.back').trigger('click')

    expect(routerPush).toHaveBeenCalledWith({ name: 'sessions' })
    expect(routerBack).not.toHaveBeenCalled()
  })

  it('renders a real <button>, not a link, so it never appears in navigation history', async () => {
    setHistoryBack('/sessions')
    const wrapper = await mountView()

    const back = wrapper.get('button.back')
    expect(back.element.tagName).toBe('BUTTON')
    expect(back.attributes('type')).toBe('button')
    expect(back.text()).toContain('All sessions')
  })
})

describe('SessionDetailView previous / next', () => {
  const item = (id: string) => ({ id }) as SessionSummaryResponse
  // Same query SessionsView builds for `/sessions?sort=recent&page=2`.
  async function mountWithCachedPage(ids: string[], back: string | null) {
    const queryClient = newTestQueryClient()
    const key = listSessionsOptions({
      query: { page: 2, per_page: 40, sort: 'recent' },
    }).queryKey
    queryClient.setQueryData(key, { items: ids.map(item), max_interest: 9, meta: {} } as never)
    setHistoryBack(back)
    return mountView(queryClient)
  }
  const links = (w: Awaited<ReturnType<typeof mountWithCachedPage>>) =>
    w.findAll('a').map((a) => `${a.text()}:${a.attributes('data-id')}`)

  it('links to the neighbours of the session in the cached list page', async () => {
    const w = await mountWithCachedPage(['a', 'sess-1', 'c'], '/sessions?sort=recent&page=2')
    expect(links(w)).toEqual(['Previous:a', 'Next:c'])
  })

  it('hides the link at the page edge', async () => {
    const w = await mountWithCachedPage(['sess-1', 'c'], '/sessions?sort=recent&page=2')
    expect(links(w)).toEqual(['Next:c'])
  })

  it('shows neither when the list page is not cached or not the origin', async () => {
    expect(links(await mountWithCachedPage(['a', 'sess-1'], '/sessions?sort=recent&page=3'))).toEqual([])
    expect(links(await mountWithCachedPage(['a', 'sess-1'], null))).toEqual([])
  })
})
