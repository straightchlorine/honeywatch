import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, Suspense } from 'vue'
import WorldMap from '@/components/map/WorldMap.vue'

vi.mock('@/components/map/useMapGeometry', () => ({
  loadMapGeometry: vi.fn(async () => ({
    width: 1600,
    height: 780,
    sphere: 'M0,0',
    graticule: 'M0,0',
    countries: ['AA', 'BB', 'CC', 'DD'].map((a2, i) => ({
      id: String(i),
      a2,
      name: a2,
      d: 'M0,0L10,0L10,10Z',
      centroid: [0, 0],
    })),
    project: () => [0, 0],
    fit: { scale: 1, translate: [0, 0] },
    disputedBorders: '',
  })),
}))

describe('WorldMap: roving tabindex', () => {
  it('has one tab stop (busiest) and arrows/Home/End move it by session count', async () => {
    const countries = [
      { a2: 'AA', sessions: 5, ips: 1, success_rate: 0 },
      { a2: 'BB', sessions: 50, ips: 1, success_rate: 0 },
      { a2: 'CC', sessions: 20, ips: 1, success_rate: 0 },
    ]
    const host = defineComponent({
      render: () =>
        h(Suspense, null, {
          default: () => h(WorldMap, { countries, cities: [], totalSessions: 75 }),
        }),
    })
    const w = mount(host, { attachTo: document.body })
    await flushPromises()
    const paths = () => w.findAll('path.country')
    const stops = () => paths().filter((p) => p.attributes('tabindex') === '0').map((p) => p.attributes('data-cid'))
    // DD has no data: tabindex -1 (never a Tab stop). BB (50) is the initial stop.
    expect(paths()[3]!.attributes('tabindex')).toBe('-1')
    expect(stops()).toEqual(['1'])
    await paths()[1]!.trigger('keydown', { key: 'ArrowDown' }) // BB -> CC
    expect(stops()).toEqual(['2'])
    await paths()[2]!.trigger('keydown', { key: 'End' }) // -> AA
    expect(stops()).toEqual(['0'])
    await paths()[0]!.trigger('keydown', { key: 'ArrowRight' }) // clamped at the end
    expect(stops()).toEqual(['0'])
    await paths()[0]!.trigger('keydown', { key: 'Home' })
    expect(stops()).toEqual(['1'])
    w.unmount()
  })
})
