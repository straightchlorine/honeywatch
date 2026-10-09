import { defineComponent, h, Suspense } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { newTestQueryClient } from '../../helpers/mount'

const { stub } = vi.hoisted(() => ({
  stub: (key: string, data: unknown) => () => ({ queryKey: [key], queryFn: async () => data }),
}))
vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  statsMapOptions: stub('map', { countries: [], cities: [] }),
  statsTotalsOptions: stub('totals', { total_sessions: 1234 }),
  statsTrendOptions: stub('trend', { current: 10, previous: 5, delta: 5, pct_change: 100 }),
  statsActivityOptions: stub('activity', []),
  statsAuthOutcomesOptions: stub('auth', { success_rate: null }),
  statsCountryDetailOptions: stub('country', {}),
}))

import OverviewView from '@/views/OverviewView.vue'

let wrapper: VueWrapper | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

async function mountOverview() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.replace('/')
  wrapper = mount(
    defineComponent({ render: () => h(Suspense, null, { default: () => h(OverviewView) }) }),
    {
      attachTo: document.body,
      global: {
        plugins: [router, [VueQueryPlugin, { queryClient: newTestQueryClient() }]],
        stubs: {
          PageShell: { template: '<div><slot name="head" /><slot /></div>' },
          TopBar: true,
          WorldMap: true,
          CountryDrawer: true,
          LiveFeed: true,
        },
      },
    },
  )
  await flushPromises()
  return wrapper
}

describe('OverviewView', () => {
  it('shows the sessions total and a "no data" accepted-login rate when the rate is null', async () => {
    const w = await mountOverview()
    expect(w.text()).toContain('1,234')
    expect(w.text()).toContain('no data')
  })

  it('explains each KPI in the tooltip when its info button takes keyboard focus', async () => {
    const w = await mountOverview()
    const btn = w.find('button[aria-label^="Unique IPs"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('focus')
    const tip = document.querySelector('.hw-tooltip')!
    expect(tip.classList.contains('show')).toBe(true)
    expect(tip.textContent).toContain('How many different addresses attacked')
    await btn.trigger('blur')
    expect(tip.classList.contains('show')).toBe(false)
  })
})
