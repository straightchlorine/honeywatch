import { defineComponent, h, Suspense } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { newTestQueryClient } from '../../helpers/mount'

const { stub, spec } = vi.hoisted(() => ({
  spec: (i: number) => ({
    sha256: String(i).repeat(64),
    name: `f${i}`,
    sessions: 3,
    machines: 2,
    first_seen: '2026-01-01T00:00:00Z',
    last_seen: '2026-01-02T00:00:00Z',
    countries: [],
    host: null,
  }),
  stub: (key: string, data: unknown) => (o: unknown) => ({
    queryKey: [key, o],
    queryFn: async () => data,
  }),
}))

vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  statsDownloadsOptions: stub('dl', [1, 2, 3].map(spec)),
  statsTcpipDestinationsOptions: stub('tcpip', []),
  statsOutcomesOptions: stub('out', {
    shell: 10,
    downloads: 3,
    tcpip: 1,
    total: 20,
    commands: 1,
    none: 1,
  }),
}))

import PayloadsView from '@/views/PayloadsView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/payloads', component: { template: '<div />' } },
    { path: '/sessions', name: 'sessions', component: { template: '<div />' } },
  ],
})

let wrapper: VueWrapper | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('PayloadsView specimens grid', () => {
  it('is one Tab stop and arrows rove between rows and the two links', async () => {
    await router.replace('/payloads')
    wrapper = mount(
      defineComponent({ render: () => h(Suspense, null, { default: () => h(PayloadsView) }) }),
      {
        attachTo: document.body,
        global: {
          plugins: [router, [VueQueryPlugin, { queryClient: newTestQueryClient() }]],
          stubs: {
            PageShell: { template: '<div><slot name="head" /><slot /></div>' },
            TopBar: true,
          },
        },
      },
    )
    await flushPromises()
    const links = () => [...document.querySelectorAll<HTMLAnchorElement>('.specimens a')]
    const stops = () => links().filter((a) => a.tabIndex === 0)
    expect(links()).toHaveLength(6)
    expect(stops()).toEqual([links()[0]])

    const press = async (key: string) => {
      document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
      await flushPromises()
    }
    links()[0]!.focus()
    await press('ArrowRight')
    expect(document.activeElement).toBe(links()[1])
    await press('ArrowDown')
    expect(document.activeElement).toBe(links()[3])
    expect(stops()).toEqual([links()[3]])
    await press('End')
    await press('Home')
    expect(document.activeElement).toBe(links()[2])
    await press('ArrowUp')
    expect(document.activeElement).toBe(links()[0])
  })
})
