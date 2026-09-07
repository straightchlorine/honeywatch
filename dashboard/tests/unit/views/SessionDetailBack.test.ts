import { defineComponent, h, Suspense } from 'vue'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import type { SessionDetailResponse } from '@/api/generated/types.gen'

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
async function mountView() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: 0 } },
  })
  const Wrapper = defineComponent({
    render: () => h(Suspense, null, { default: () => h(SessionDetailView) }),
  })
  const wrapper = mount(Wrapper, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        PageShell: { template: '<div><slot /></div>' },
        SessionTerminal: true,
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
