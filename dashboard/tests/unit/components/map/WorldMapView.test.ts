import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorldMapView from '@/components/map/WorldMapView.vue'
import type { WorldGeometry } from '@/components/map/useWorldGeometry'

const GEOMETRY: WorldGeometry = {
  width: 975,
  height: 460,
  sphere: 'M0,0',
  graticule: 'M0,0',
  borders: 'M0,0',
  coast: 'M0,0',
  countries: [
    { id: '840', name: 'United States', d: 'M1,1L2,2Z' },
    { id: '156', name: 'China', d: 'M3,3L4,4Z' },
    { id: '004', name: 'Afghanistan', d: 'M5,5L6,6Z' },
  ],
}

function mountMap(counts: Map<string, number>) {
  return mount(WorldMapView, { props: { geometry: GEOMETRY, counts } })
}

describe('WorldMapView', () => {
  it('renders one path per country', () => {
    const wrapper = mountMap(new Map([['156', 1200]]))
    expect(wrapper.findAll('.country')).toHaveLength(3)
  })

  it('paints attacked countries with the ramp and others with the land color', () => {
    const wrapper = mountMap(new Map([['156', 1200]]))
    const paths = wrapper.findAll('.country')
    const fill = (i: number) => paths[i]!.attributes('fill')
    // China (index 1) is attacked -> ramp; US/AF -> land.
    expect(fill(1)).toContain('color-mix')
    expect(fill(0)).toBe('var(--map-land)')
    expect(fill(2)).toBe('var(--map-land)')
  })

  it('summarizes the top sources in the role=img aria-label', () => {
    const wrapper = mountMap(
      new Map([
        ['156', 1200],
        ['840', 400],
      ]),
    )
    const label = wrapper.find('svg').attributes('aria-label') ?? ''
    expect(label).toContain('China 1,200')
    expect(label).toContain('United States 400')
    expect(label).toContain('2 countries with activity')
  })

  it('lists attacked countries in an offscreen accessible fallback', () => {
    const wrapper = mountMap(new Map([['156', 1200]]))
    const items = wrapper.findAll('.visually-hidden li')
    expect(items).toHaveLength(1)
    expect(items[0]!.text()).toContain('China')
    expect(items[0]!.text()).toContain('1,200')
  })

  it('reports no activity when there are no counts', () => {
    const wrapper = mountMap(new Map())
    expect(wrapper.find('svg').attributes('aria-label')).toContain('No attacks recorded yet')
    expect(wrapper.findAll('.visually-hidden li')).toHaveLength(0)
  })

  it('shows a themed tooltip on hover', async () => {
    const wrapper = mountMap(new Map([['156', 1200]]))
    await wrapper.findAll('.country')[1]!.trigger('mouseenter')
    const tip = wrapper.find('.tooltip')
    expect(tip.exists()).toBe(true)
    expect(tip.text()).toContain('China')
    expect(tip.text()).toContain('1,200 sessions')
  })
})
