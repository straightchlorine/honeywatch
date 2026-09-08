import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChipSelect from '@/components/base/ChipSelect.vue'

const options = [
  { value: 'sessions', label: 'Sessions' },
  { value: 'ips', label: 'Unique IPs' },
]

describe('ChipSelect', () => {
  it('renders one option per entry', async () => {
    const w = mount(ChipSelect, {
      props: { modelValue: 'sessions', options, label: 'Sort by' },
    })
    await w.find('.dd-button').trigger('click')
    expect(w.findAll('[role=option]')).toHaveLength(2)
  })

  it('reflects modelValue as the trigger label', () => {
    const w = mount(ChipSelect, { props: { modelValue: 'ips', options, label: 'Sort by' } })
    expect(w.find('.dd-button').text()).toContain('Unique IPs')
  })

  it('emits update:modelValue when an option is clicked', async () => {
    const w = mount(ChipSelect, {
      props: { modelValue: 'sessions', options, label: 'Sort by' },
    })
    await w.find('.dd-button').trigger('click')
    await w.findAll('[role=option]')[1]!.trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['ips'])
  })

  it('exposes an accessible name via a visually-hidden label', () => {
    const w = mount(ChipSelect, {
      props: { modelValue: 'sessions', options, label: 'Sort by' },
    })
    const label = w.find('.visually-hidden')
    expect(label.text()).toBe('Sort by')
    expect(w.find('.dd-button').attributes('aria-labelledby')).toContain(label.attributes('id'))
  })
})
