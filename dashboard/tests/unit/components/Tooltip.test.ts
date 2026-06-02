import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import Tooltip from '@/components/base/Tooltip.vue'

afterEach(() => {
  document.body.innerHTML = ''
})

describe('Tooltip', () => {
  it('teleports a role=tooltip bubble with the text when visible', () => {
    mount(Tooltip, { props: { visible: true, x: 10, y: 20, text: 'root:123456' } })
    const el = document.body.querySelector('.tooltip')
    expect(el).not.toBeNull()
    expect(el?.getAttribute('role')).toBe('tooltip')
    expect(el?.textContent).toContain('root:123456')
  })

  it('renders nothing when not visible', () => {
    mount(Tooltip, { props: { visible: false, x: 0, y: 0, text: 'hidden' } })
    expect(document.body.querySelector('.tooltip')).toBeNull()
  })

  it('lets slot content override the text prop', () => {
    mount(Tooltip, {
      props: { visible: true, x: 0, y: 0, text: 'fallback' },
      slots: { default: '<b class="slotted">custom</b>' },
    })
    const el = document.body.querySelector('.tooltip')
    expect(el?.querySelector('.slotted')).not.toBeNull()
    expect(el?.textContent).toContain('custom')
    expect(el?.textContent).not.toContain('fallback')
  })

  it('appears when visibility flips on after mount', async () => {
    const w = mount(Tooltip, { props: { visible: false, x: 5, y: 5, text: 'later' } })
    expect(document.body.querySelector('.tooltip')).toBeNull()
    await w.setProps({ visible: true })
    expect(document.body.querySelector('.tooltip')?.textContent).toContain('later')
  })
})
