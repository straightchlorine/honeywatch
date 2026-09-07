import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChipButton from '@/components/base/ChipButton.vue'

describe('ChipButton', () => {
  it('renders as before with no slot content', () => {
    const w = mount(ChipButton, { slots: { default: 'Label' } })
    expect(w.find('button.chip').exists()).toBe(true)
    expect(w.text()).toBe('Label')
    expect(w.find('.chip-trailing').exists()).toBe(false)
  })

  it('renders trailing slot content inside the control with no nested button', () => {
    const w = mount(ChipButton, {
      slots: {
        default: 'Label',
        trailing: '<button type="button" class="info-dot">i</button>',
      },
    })

    expect(w.find('.chip-trailing').exists()).toBe(true)
    expect(w.find('.chip-trailing .info-dot').exists()).toBe(true)

    const buttons = w.findAll('button')
    for (const b of buttons) {
      expect(b.find('button').exists()).toBe(false)
    }
  })

  it('emits toggle when the chip button is clicked', async () => {
    const w = mount(ChipButton, { slots: { default: 'Label' } })
    await w.find('button.chip').trigger('click')
    expect(w.emitted('toggle')).toHaveLength(1)
  })
})
