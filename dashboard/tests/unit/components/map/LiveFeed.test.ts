import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import LiveFeed from '@/components/map/LiveFeed.vue'

const state = {
  data: ref<unknown>(undefined),
  isError: ref(false),
  isPending: ref(false),
}

vi.mock('@tanstack/vue-query', () => ({ useQuery: () => state }))
vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({ listSessionsOptions: () => ({}) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

function setState(s: { data?: unknown; isError?: boolean; isPending?: boolean }): void {
  state.data.value = s.data
  state.isError.value = s.isError ?? false
  state.isPending.value = s.isPending ?? false
}

const status = () => mount(LiveFeed).get('[role="status"]')

describe('LiveFeed status line', () => {
  beforeEach(() => setState({}))

  it('reports a load error', () => {
    setState({ isError: true })
    expect(status().text()).toBe('Could not load live sessions. Retrying.')
  })

  it('reports loading while pending', () => {
    setState({ isPending: true })
    expect(status().text()).toBe('Loading sessions...')
  })

  it('reports an empty feed', () => {
    setState({ data: { items: [] } })
    expect(status().text()).toBe('No sessions yet.')
  })

  it('stays mounted but empty once rows exist, and its text changes in place', async () => {
    setState({ isPending: true })
    const w = mount(LiveFeed)
    const el = w.get('[role="status"]').element
    expect(el.textContent).toBe('Loading sessions...')
    state.isPending.value = false
    state.data.value = {
      items: [
        {
          id: 's1',
          started_at: '2026-01-01T10:00:00Z',
          country_code: 'DE',
          country: 'Germany',
          city: null,
          protocol: 'ssh',
          category: 'active',
          has_successful_login: true,
          lat: null,
          lon: null,
        },
      ],
    }
    await w.vm.$nextTick()
    expect(w.get('[role="status"]').element).toBe(el)
    expect(el.textContent).toBe('')
    expect(w.findAll('.feed-row')).toHaveLength(1)
  })
})
