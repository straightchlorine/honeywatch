import { describe, expect, it } from 'vitest'

import { useTooltip } from '@/components/base/useTooltip'

describe('useTooltip', () => {
  it('starts hidden', () => {
    const { state } = useTooltip()
    expect(state.visible).toBe(false)
  })

  it('show() captures the text and cursor coordinates', () => {
    const tt = useTooltip()
    tt.show('root:123456', new MouseEvent('mouseenter', { clientX: 12, clientY: 34 }))
    expect(tt.state).toMatchObject({ visible: true, text: 'root:123456', x: 12, y: 34 })
  })

  it('hide() clears visibility', () => {
    const tt = useTooltip()
    tt.show('x', new MouseEvent('mousemove', { clientX: 1, clientY: 2 }))
    tt.hide()
    expect(tt.state.visible).toBe(false)
  })

  it('anchors to the focused element when there are no cursor coordinates', () => {
    const tt = useTooltip()
    const el = document.createElement('button')
    el.getBoundingClientRect = () => ({ left: 10, top: 20, width: 40, height: 8 }) as DOMRect
    // A focus event carries no clientX/clientY, so it anchors to the element rect.
    tt.show('len 6', { currentTarget: el } as unknown as FocusEvent)
    expect(tt.state).toMatchObject({ visible: true, text: 'len 6', x: 30, y: 20 })
  })

  it('dismisses on a pointerdown anywhere (no stuck bubble after a click)', () => {
    const tt = useTooltip()
    tt.show('root:123456', new MouseEvent('mouseenter', { clientX: 5, clientY: 6 }))
    expect(tt.state.visible).toBe(true)
    document.dispatchEvent(new Event('pointerdown'))
    expect(tt.state.visible).toBe(false)
  })

  it('suppresses the tooltip on touch-primary (hover: none) devices', () => {
    const original = window.matchMedia
    window.matchMedia = ((q: string) =>
      ({ matches: q.includes('hover: none'), media: q }) as MediaQueryList) as typeof matchMedia
    try {
      const tt = useTooltip()
      tt.show('root:123456', new MouseEvent('mouseenter', { clientX: 5, clientY: 6 }))
      expect(tt.state.visible).toBe(false)
    } finally {
      window.matchMedia = original
    }
  })
})
