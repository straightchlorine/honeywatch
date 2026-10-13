import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

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

  it('puts the sparkline after the meta so captions share rows across tiles', () => {
    const w = mount(StatTile, {
      props: { label: 'X', value: '1', spark: [1, 2, 3] },
      slots: { meta: '3.16% accepted' },
    })
    const order = w.findAll('.value, .meta, .spark').map((n) => n.classes()[0])
    expect(order).toEqual(['value', 'meta', 'spark'])
  })

  it('keeps the label-extra slot inside the label tail so it wraps with the last word', () => {
    const w = mount(StatTile, {
      props: { label: 'Distinct passwords', value: '1' },
      slots: { 'label-extra': '<button class="dot"></button>' },
    })
    expect(w.find('.tail').text()).toBe('passwords')
    expect(w.find('.tail .dot').exists()).toBe(true)
  })

  it('renders a phone label beside the full one, with the info dot after it', () => {
    const w = mount(StatTile, {
      props: { label: 'Login attempts', short: 'Attempts', value: '1' },
      slots: { 'label-extra': '<button class="dot"></button>' },
    })
    expect(w.find('.l-short').text()).toBe('Attempts')
    expect(w.findAll('.l-full').map((n) => n.text())).toEqual(['Login', 'attempts'])
    expect(w.findAll('.dot')).toHaveLength(1)
  })

  it('splits a single-word label so the info dot rides with its last letter', () => {
    const w = mount(StatTile, {
      props: { label: 'Sessions', value: '1' },
      slots: { 'label-extra': '<button class="dot"></button>' },
    })
    expect(w.find('.tail').text()).toBe('s')
    expect(w.find('.tail .dot').exists()).toBe(true)
  })

  it('observes the sparkline wrapper when spark arrives after mount', async () => {
    const created: number[] = []
    const observed: Element[] = []
    const disconnects = { count: 0 }
    class FakeResizeObserver {
      constructor() {
        created.push(created.length)
      }
      observe(el: Element) {
        observed.push(el)
      }
      unobserve() {}
      disconnect() {
        disconnects.count++
      }
    }
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    try {
      const w = mount(StatTile, { props: { label: 'X', value: '1' } })
      expect(created).toHaveLength(0)

      await w.setProps({ spark: [1, 2, 3] })
      expect(created).toHaveLength(1)
      expect(observed).toEqual([w.find('.spark').element])

      await w.setProps({ spark: undefined })
      expect(disconnects.count).toBe(1)
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
