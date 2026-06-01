import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import Dropdown from '@/components/base/Dropdown.vue'

const OPTIONS = [
  { value: '', label: 'All' },
  { value: 'a', label: 'Active' },
  { value: 'b', label: 'Probe' },
]

function mountDd(modelValue = '') {
  return mount(Dropdown, {
    props: { modelValue, options: OPTIONS, buttonId: 'f', labelId: 'lbl' },
  })
}

describe('Dropdown', () => {
  it('shows the selected option label on the trigger', () => {
    expect(mountDd('a').find('.dd-button').text()).toContain('Active')
  })

  it('opens the listbox on click and lists every option', async () => {
    const w = mountDd()
    expect(w.find('[role=listbox]').exists()).toBe(false)
    await w.find('.dd-button').trigger('click')
    expect(w.find('[role=listbox]').exists()).toBe(true)
    expect(w.findAll('[role=option]')).toHaveLength(3)
    expect(w.find('.dd-button').attributes('aria-expanded')).toBe('true')
  })

  it('emits update:modelValue when an option is clicked', async () => {
    const w = mountDd()
    await w.find('.dd-button').trigger('click')
    await w.findAll('[role=option]')[1]!.trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['a'])
  })

  it('marks the current value with aria-selected', async () => {
    const w = mountDd('b')
    await w.find('.dd-button').trigger('click')
    const opts = w.findAll('[role=option]')
    expect(opts[2]!.attributes('aria-selected')).toBe('true')
    expect(opts[0]!.attributes('aria-selected')).toBe('false')
  })

  it('selects via keyboard (ArrowDown then Enter)', async () => {
    const w = mountDd() // active starts at selected index 0
    await w.find('.dd-button').trigger('click')
    const list = w.find('[role=listbox]')
    await list.trigger('keydown', { key: 'ArrowDown' })
    await list.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['a'])
  })

  it('closes on Escape', async () => {
    const w = mountDd()
    await w.find('.dd-button').trigger('click')
    expect(w.find('[role=listbox]').exists()).toBe(true)
    await w.find('[role=listbox]').trigger('keydown', { key: 'Escape' })
    expect(w.find('[role=listbox]').exists()).toBe(false)
  })
})
