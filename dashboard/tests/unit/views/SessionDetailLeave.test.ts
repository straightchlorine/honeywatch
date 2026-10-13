import { defineComponent, h, reactive, Suspense } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import type { SessionDetailResponse } from '@/api/generated/types.gen'
import { newTestQueryClient } from '../../helpers/mount'

// The route object is shared and reactive, like vue-router's, so the view sees it move on.
const route = reactive<{ params: Record<string, string>; meta: object }>({
  params: { id: 'sess-1' },
  meta: {},
})
const requested: string[] = []

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

vi.mock('@/api/queries', () => ({
  getSessionByIdOptions: ({ path }: { path: { session_id: string } }) => ({
    queryKey: ['session', path.session_id],
    queryFn: async (): Promise<SessionDetailResponse> => {
      requested.push(path.session_id)
      return { ...SESSION, id: path.session_id }
    },
  }),
}))

import SessionDetailView from '@/views/SessionDetailView.vue'
import { takeLastViewed } from '@/utils/lastViewed'

const SESSION: SessionDetailResponse = {
  id: 'sess-1',
  src_port: 51234,
  dst_port: 22,
  protocol: 'ssh',
  sensor: 'edge-01',
  interest: 0,
  max_interest: 0,
  country: null,
  country_code: null,
  city: null,
  lat: null,
  lon: null,
  started_at: '2026-05-31T13:40:00Z',
  ended_at: '2026-05-31T13:42:00Z',
  auth_attempts: [],
  commands: [],
  downloads: [],
}

const Wrapper = defineComponent({
  render: () => h(Suspense, null, { default: () => h(SessionDetailView) }),
})

// Unmount each view after its test so a leftover instance cannot watch the shared route.
const mounted: { unmount(): void }[] = []
function mountView() {
  const wrapper = mount(Wrapper, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient: newTestQueryClient() }]],
      stubs: { PageShell: { template: '<div><slot /></div>' }, SessionTerminal: true },
    },
  })
  mounted.push(wrapper)
  return wrapper
}

describe('SessionDetailView while the next page loads', () => {
  beforeEach(() => {
    requested.length = 0
    // Drop whatever an earlier test left in the shared last-viewed slot.
    takeLastViewed()
  })

  afterEach(() => {
    for (const wrapper of mounted.splice(0)) wrapper.unmount()
  })

  it('keeps its session instead of fetching an empty id once the route has left', async () => {
    mountView()
    await flushPromises()
    expect(requested).toEqual(['sess-1'])

    // Leaving for another page: the old view stays mounted until the new one has loaded.
    route.params = {}
    await flushPromises()
    expect(requested).toEqual(['sess-1'])

    // Previous/Next reuse the instance, so a new id still loads.
    route.params = { id: 'sess-2' }
    await flushPromises()
    expect(requested).toEqual(['sess-1', 'sess-2'])
  })

  it('records the viewed session so the list can return focus to its row', async () => {
    route.params = { id: 'sess-1' }
    mountView()
    await flushPromises()
    route.params = { id: 'sess-2' }
    await flushPromises()
    expect(takeLastViewed()).toBe('sess-2')
    expect(takeLastViewed()).toBeNull()
  })
})
