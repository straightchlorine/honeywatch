import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatTile from '@/components/base/StatTile.vue'

describe('StatTile', () => {
  it('renders the label and value', () => {
    const w = mount(StatTile, { props: { label: 'Sessions', value: '344,019' } })
    expect(w.text()).toContain('Sessions')
    expect(w.text()).toContain('344,019')
  })

  it('renders a sparkline when 2+ spark values are given', () => {
    const w = mount(StatTile, { props: { label: 'X', value: '1', spark: [1, 2, 3] } })
    expect(w.find('svg').exists()).toBe(true)
  })

  it('omits the sparkline for a single value', () => {
    const w = mount(StatTile, { props: { label: 'X', value: '1', spark: [1] } })
    expect(w.find('svg').exists()).toBe(false)
  })

  it('applies the glass variant class when requested', () => {
    const w = mount(StatTile, { props: { label: 'X', value: '1', glass: true } })
    expect(w.find('.stat-tile').classes()).toContain('glass')
  })

  it('renders the meta slot only when provided', () => {
    const without = mount(StatTile, { props: { label: 'X', value: '1' } })
    expect(without.find('.meta').exists()).toBe(false)

    const withMeta = mount(StatTile, {
      props: { label: 'X', value: '1' },
      slots: { meta: '3.16% accepted' },
    })
    expect(withMeta.find('.meta').text()).toBe('3.16% accepted')
  })
})
