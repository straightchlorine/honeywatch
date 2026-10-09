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
    countries: ['AA', 'BB', 'CC', 'DD', 'EE'].map((a2, i) => ({
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

type Row = { a2: string; sessions: number; ips: number; success_rate: number }
const row = (a2: string, sessions: number): Row => ({ a2, sessions, ips: 1, success_rate: 0 })

async function mountMap(countries: Row[], cities: unknown[] = []) {
  const host = defineComponent({
    props: { countries: { type: Array, required: true } },
    emits: ['select'],
    setup: (p, { emit }) => () =>
      h(Suspense, null, {
        default: () =>
          h(WorldMap, {
            countries: p.countries as Row[],
            cities: cities as never[],
            totalSessions: 75,
            onSelect: (a2: string) => emit('select', a2),
          }),
      }),
  })
  const w = mount(host, { attachTo: document.body, props: { countries } })
  await flushPromises()
  const paths = () => w.findAll('path.country')
  const stops = () =>
    paths()
      .filter((p) => p.attributes('tabindex') === '0')
      .map((p) => p.attributes('data-cid'))
  return { w, paths, stops }
}

const THREE = [row('AA', 5), row('BB', 50), row('CC', 20)]

describe('WorldMap: roving tabindex', () => {
  it('has one tab stop (busiest) and arrows/Home/End move it by session count', async () => {
    const { w, paths, stops } = await mountMap(THREE)
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

  it('ArrowUp and ArrowLeft walk back toward the busiest', async () => {
    const { w, paths, stops } = await mountMap(THREE)
    await paths()[1]!.trigger('keydown', { key: 'End' }) // -> AA (last)
    await paths()[0]!.trigger('keydown', { key: 'ArrowUp' }) // AA -> CC
    expect(stops()).toEqual(['2'])
    await paths()[2]!.trigger('keydown', { key: 'ArrowLeft' }) // CC -> BB
    expect(stops()).toEqual(['1'])
    await paths()[1]!.trigger('keydown', { key: 'ArrowLeft' }) // clamped at the start
    expect(stops()).toEqual(['1'])
    w.unmount()
  })

  it('Enter and Space select the country; no-data countries do nothing', async () => {
    const { w, paths } = await mountMap(THREE)
    await paths()[1]!.trigger('keydown', { key: 'Enter' })
    await paths()[2]!.trigger('keydown', { key: ' ' })
    await paths()[3]!.trigger('keydown', { key: 'Enter' }) // DD: no data
    expect(w.emitted('select')).toEqual([['BB'], ['CC']])
    w.unmount()
  })

  it('navigation skips countries without data', async () => {
    // AA and EE have data, BB..DD sit between them in path order but have none.
    const { w, paths, stops } = await mountMap([row('AA', 10), row('EE', 5)])
    expect(stops()).toEqual(['0'])
    await paths()[0]!.trigger('keydown', { key: 'ArrowDown' })
    expect(stops()).toEqual(['4'])
    w.unmount()
  })

  it('keeps exactly one tab stop when the countries prop changes', async () => {
    const { w, paths, stops } = await mountMap(THREE)
    await paths()[1]!.trigger('keydown', { key: 'ArrowDown' }) // stop on CC
    expect(stops()).toEqual(['2'])
    // CC loses its data: the roving id is stale and must fall back to the busiest.
    await w.setProps({ countries: [row('AA', 5), row('BB', 50)] })
    expect(stops()).toEqual(['1'])
    // The stale id (CC) is still invalid, so a busier newcomer becomes the stop.
    await w.setProps({ countries: [row('AA', 5), row('BB', 50), row('DD', 99)] })
    expect(stops()).toEqual(['3'])
    w.unmount()
  })

  it('labels the group as ordered by sessions', async () => {
    const { w } = await mountMap(THREE)
    expect(w.get('[role="group"]').attributes('aria-label')).toContain('ordered by sessions')
    w.unmount()
  })

  it('has exactly one tab stop across country paths and city hit circles', async () => {
    const cities = [
      { city: 'X', country_code: 'BB', lat: 1, lon: 1, sessions: 9 },
      { city: 'Y', country_code: 'CC', lat: 2, lon: 2, sessions: 4 },
    ]
    const { w } = await mountMap(THREE, cities)
    expect(w.findAll('circle.city-hit')).toHaveLength(2)
    const tabbable = w.findAll('path.country, circle.city-hit').filter((e) => e.attributes('tabindex') === '0')
    expect(tabbable).toHaveLength(1)
    w.unmount()
  })
})
