import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import InfoDot from '@/components/base/InfoDot.vue'

const tt = vi.hoisted(() => ({
  show: vi.fn(),
  showAt: vi.fn(),
  move: vi.fn(),
  hide: vi.fn(),
}))

vi.mock('@/composables/useHwTooltip', () => ({
  useHwTooltip: () => tt,
}))

const props = { title: 'Sessions', text: 'Each connection to the honeypot.' }

describe('InfoDot', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('opens the tooltip with the button and text on focus', async () => {
    const w = mount(InfoDot, { props })
    await w.find('button').trigger('focus')
    expect(tt.showAt).toHaveBeenCalledTimes(1)
    const [el, title, rows] = tt.showAt.mock.calls[0]!
    expect(el).toBe(w.find('button').element)
    expect(title).toBe(props.title)
    expect(rows).toEqual([['', props.text]])
  })

  it('hides the tooltip on blur', async () => {
    const w = mount(InfoDot, { props })
    await w.find('button').trigger('blur')
    expect(tt.hide).toHaveBeenCalledTimes(1)
  })

  it('hides the tooltip when Escape is pressed', async () => {
    const w = mount(InfoDot, { props })
    await w.find('button').trigger('keydown', { key: 'Escape' })
    expect(tt.hide).toHaveBeenCalledTimes(1)
  })

  it('ignores other keys', async () => {
    const w = mount(InfoDot, { props })
    await w.find('button').trigger('keydown', { key: 'Enter' })
    expect(tt.hide).not.toHaveBeenCalled()
  })
})
