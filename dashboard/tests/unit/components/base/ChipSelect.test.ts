import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChipSelect from '@/components/base/ChipSelect.vue'

const options = [
  { value: 'sessions', label: 'Sessions' },
  { value: 'ips', label: 'Unique IPs' },
]

describe('ChipSelect', () => {
  it('forwards options and modelValue to the rendered Dropdown', async () => {
    const w = mount(ChipSelect, { props: { modelValue: 'ips', options, label: 'Sort by' } })
    expect(w.find('.dd-button').text()).toContain('Unique IPs')
    await w.find('.dd-button').trigger('click')
    const opts = w.findAll('[role=option]')
    expect(opts).toHaveLength(2)
    await opts[0]!.trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['sessions'])
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
