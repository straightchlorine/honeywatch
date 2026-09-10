import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SortableTh from '@/components/base/SortableTh.vue'

describe('SortableTh', () => {
  it('renders a plain th with no button when sortKey is omitted', () => {
    const w = mount(SortableTh, {
      props: { modelValue: 'sessions' },
      slots: { default: 'Column' },
    })
    expect(w.find('th').exists()).toBe(true)
    expect(w.find('button').exists()).toBe(false)
    expect(w.text()).toContain('Column')
  })

  it('emits aria-sort=descending on the active column when dir=desc', () => {
    const w = mount(SortableTh, {
      props: { sort: 'sessions', sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('descending')
  })

  it('emits aria-sort=ascending on the active column when dir=asc', () => {
    const w = mount(SortableTh, {
      props: { sort: 'sessions', sortKey: 'sessions', dir: 'asc' },
      slots: { default: 'Sessions' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('ascending')
  })

  it('omits aria-sort on inactive columns', () => {
    const w = mount(SortableTh, {
      props: { sort: 'sessions', sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w.find('th').attributes('aria-sort')).toBeUndefined()
  })

  it('click 1: sets sort and order to natural direction', async () => {
    const w = mount(SortableTh, {
      props: { sort: undefined, order: undefined, sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    await w.find('button').trigger('click')
    expect(w.emitted('update:sort')?.[0]).toEqual(['attempts'])
    expect(w.emitted('update:order')?.[0]).toEqual(['desc'])
  })

  it('click 2: flips order when already at natural direction', async () => {
    const w = mount(SortableTh, {
      props: { sort: 'attempts', order: undefined, sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('descending')
    await w.find('button').trigger('click')
    expect(w.emitted('update:order')?.[0]).toEqual(['asc'])
  })

  it('click 3: clears both sort and order when already flipped', async () => {
    const w = mount(SortableTh, {
      props: { sort: 'attempts', order: 'asc', sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('ascending')
    await w.find('button').trigger('click')
    expect(w.emitted('update:sort')?.[0]).toEqual([undefined])
    expect(w.emitted('update:order')?.[0]).toEqual([undefined])
  })

  it('aria-sort follows resolved direction (order ?? dir)', async () => {
    // Natural direction: no order set
    const w1 = mount(SortableTh, {
      props: { sort: 'attempts', order: undefined, sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w1.find('th').attributes('aria-sort')).toBe('descending')

    // Flipped direction: order explicitly set
    const w2 = mount(SortableTh, {
      props: { sort: 'attempts', order: 'asc', sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w2.find('th').attributes('aria-sort')).toBe('ascending')
  })

  it('clicking a different column resets order to its natural direction', async () => {
    const w = mount(SortableTh, {
      props: { sort: 'attempts', order: 'asc', sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    await w.find('button').trigger('click')
    expect(w.emitted('update:sort')?.[0]).toEqual(['sessions'])
    expect(w.emitted('update:order')?.[0]).toEqual(['desc'])
  })

  it('visually-hidden text describes current state and next action', async () => {
    // Inactive column
    const w1 = mount(SortableTh, {
      props: { sort: 'attempts', order: undefined, sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    expect(w1.find('.visually-hidden').text()).toBe('Sort by this column')

    // Active, at natural direction
    const w2 = mount(SortableTh, {
      props: { sort: 'sessions', order: undefined, sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    expect(w2.find('.visually-hidden').text()).toBe('sorted descending, Sort in reverse')

    // Active, flipped
    const w3 = mount(SortableTh, {
      props: { sort: 'sessions', order: 'asc', sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    expect(w3.find('.visually-hidden').text()).toBe('sorted ascending, Clear sort')
  })
})
