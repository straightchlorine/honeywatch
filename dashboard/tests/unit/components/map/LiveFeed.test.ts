import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

describe('LiveFeed country label', () => {
  beforeEach(() => setState({}))

  function session(overrides: Record<string, unknown>) {
    return {
      id: 's2',
      started_at: '2026-01-01T10:00:00Z',
      country_code: 'FR',
      country: 'France',
      city: null,
      protocol: 'ssh',
      category: 'active',
      has_successful_login: true,
      lat: null,
      lon: null,
      ...overrides,
    }
  }

  it('shows the city as the visible place, with the country as title and suffix', () => {
    setState({ data: { items: [session({ city: 'Paris' })] } })
    const label = mount(LiveFeed).get('.feed-row .country')
    expect(label.attributes('title')).toBe('Paris, France')
    expect(label.element.firstChild?.textContent).toBe('Paris')
    expect(label.get('.cn').text()).toBe(', France')
  })

  it('falls back to the country when the city is null', () => {
    setState({ data: { items: [session({ city: null })] } })
    const label = mount(LiveFeed).get('.feed-row .country')
    expect(label.text()).toBe('France')
    expect(label.attributes('title')).toBe('France')
    expect(label.find('.cn').exists()).toBe(false)
  })
})

describe('LiveFeed freshness', () => {
  beforeEach(() => setState({}))
  const item = (iso: string) => ({
    id: 'f',
    started_at: iso,
    country_code: 'FR',
    country: 'France',
    city: null,
    protocol: 'ssh',
    category: 'active',
    has_successful_login: true,
    lat: null,
    lon: null,
  })

  it('greys the dot and shows the age when the newest session is stale', () => {
    setState({ data: { items: [item(new Date(Date.now() - 11 * 86_400_000).toISOString())] } })
    const w = mount(LiveFeed)
    expect(w.get('.stale').text()).toBe('last 11d ago')
    expect(w.get('.live-dot').classes()).toContain('paused')
  })

  it('keeps the pulsing dot and no age when fresh', () => {
    setState({ data: { items: [item(new Date(Date.now() - 60_000).toISOString())] } })
    const w = mount(LiveFeed)
    expect(w.find('.stale').exists()).toBe(false)
    expect(w.get('.live-dot').classes()).not.toContain('paused')
  })

  describe('15 minute boundary', () => {
    const T0 = new Date('2026-01-01T12:00:00Z')
    const ago = (min: number) => new Date(T0.getTime() - min * 60_000).toISOString()
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(T0)
    })
    afterEach(() => vi.useRealTimers())

    it('shows no cue at 14 minutes and a cue at 16', () => {
      setState({ data: { items: [item(ago(14))] } })
      expect(mount(LiveFeed).find('.stale').exists()).toBe(false)
      setState({ data: { items: [item(ago(16))] } })
      expect(mount(LiveFeed).get('.stale').text()).toBe('last 16m ago')
    })

    it('shows the cue once time passes with unchanged data', async () => {
      setState({ data: { items: [item(ago(14))] } })
      const w = mount(LiveFeed)
      expect(w.find('.stale').exists()).toBe(false)
      await vi.advanceTimersByTimeAsync(2 * 60_000)
      expect(w.get('.stale').text()).toBe('last 16m ago')
    })
  })
})
