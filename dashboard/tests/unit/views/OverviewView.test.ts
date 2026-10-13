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

  it('keeps the DOM Sessions-first so the desktop stack leads with Sessions', async () => {
    const w = await mountOverview()
    const labels = w.findAll('.kpis .stat-tile .label').map((l) => l.text())
    expect(labels.map((t) => t.split(' ').slice(0, 2).join(' '))).toEqual([
      'Sessions',
      'Logins',
      'Unique IPs',
    ])
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

  it('closes a focus-opened tooltip when Escape is pressed', async () => {
    const w = await mountOverview()
    const btn = w.find('button[aria-label^="Sessions"]')
    await btn.trigger('focus')
    const tip = document.querySelector('.hw-tooltip')!
    expect(tip.classList.contains('show')).toBe(true)
    await btn.trigger('keydown', { key: 'Escape' })
    expect(tip.classList.contains('show')).toBe(false)
  })

  it('labels each info button with its title and explanation', async () => {
    const w = await mountOverview()
    expect(w.get('button[aria-label^="Sessions"]').attributes('aria-label')).toBe(
      'Sessions: One session is one visit to the honeypot, from connecting to leaving. Below: sessions this week, and the change from the week before.',
    )
  })

  it('shows the weekly count and only the percentage, tinted by direction', async () => {
    const w = await mountOverview()
    expect(w.get('.trend-tip').text()).toBe('10\u00b7+100%')
    expect(w.get('.trend-tip').attributes('aria-label')).toContain('vs prior week')
    expect(w.get('.trend-pct').text()).toBe('+100%')
  })
})
