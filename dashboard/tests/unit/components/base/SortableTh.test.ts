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
      props: { modelValue: 'sessions', sortKey: 'sessions', dir: 'desc' },
      slots: { default: 'Sessions' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('descending')
  })

  it('emits aria-sort=ascending on the active column when dir=asc', () => {
    const w = mount(SortableTh, {
      props: { modelValue: 'sessions', sortKey: 'sessions', dir: 'asc' },
      slots: { default: 'Sessions' },
    })
    expect(w.find('th').attributes('aria-sort')).toBe('ascending')
  })

  it('omits aria-sort on inactive columns', () => {
    const w = mount(SortableTh, {
      props: { modelValue: 'sessions', sortKey: 'attempts', dir: 'desc' },
      slots: { default: 'Attempts' },
    })
    expect(w.find('th').attributes('aria-sort')).toBeUndefined()
  })

  it('updates the model when the button is clicked', async () => {
    const w = mount(SortableTh, {
      props: { modelValue: 'sessions', sortKey: 'attempts' },
      slots: { default: 'Attempts' },
    })
    await w.find('button').trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['attempts'])
  })
})
