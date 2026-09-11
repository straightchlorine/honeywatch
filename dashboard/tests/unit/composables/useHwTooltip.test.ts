import { describe, expect, it, afterEach, vi } from 'vitest'
import { useHwTooltip } from '@/composables/useHwTooltip'
import { stubMatchMedia } from '../../setup'

describe('useHwTooltip', () => {
  afterEach(() => {
    const el = document.querySelector('.hw-tooltip')
    if (el) {
      el.classList.remove('show')
      el.replaceChildren()
      el.removeAttribute('style')
    }
    vi.clearAllMocks()
  })

  it('creates the DOM node on first show()', () => {
    expect(document.querySelector('.hw-tooltip')).toBe(null)
    const tt = useHwTooltip()
    tt.show('Test')
    expect(document.querySelector('.hw-tooltip')).not.toBe(null)
  })

  it('shows a tooltip with title text only', () => {
    const tt = useHwTooltip()
    tt.show('Hello World')
    const node = document.querySelector('.hw-tooltip')!
    expect(node).not.toBe(null)
    expect(node.classList.contains('show')).toBe(true)
    const title = node.querySelector('.tt-title')
    expect(title?.textContent).toBe('Hello World')
  })

  it('shows a tooltip with title and icon', () => {
    const tt = useHwTooltip()
    tt.show('My Title', [], 'E')
    const node = document.querySelector('.hw-tooltip')!
    const title = node.querySelector('.tt-title')!
    const icon = title.querySelector('span')
    expect(icon?.textContent).toBe('E')
    expect(title.textContent).toContain('E')
    expect(title.textContent).toContain('My Title')
  })

  it('renders tooltip rows with label and value', () => {
    const tt = useHwTooltip()
    tt.show('Title', [
      ['Label 1', 'Value 1'],
      ['Label 2', 'Value 2'],
    ])
    const node = document.querySelector('.hw-tooltip')!
    const rows = node.querySelectorAll('.tt-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.querySelector('span')?.textContent).toBe('Label 1')
    expect(rows[0]?.querySelector('b')?.textContent).toBe('Value 1')
    expect(rows[1]?.querySelector('span')?.textContent).toBe('Label 2')
    expect(rows[1]?.querySelector('b')?.textContent).toBe('Value 2')
  })

  it('applies variant CSS classes to row values', () => {
    const tt = useHwTooltip()
    tt.show('Title', [
      ['Pos', '10', 'pos'],
      ['Neg', '-5', 'neg'],
    ])
    const node = document.querySelector('.hw-tooltip')!
    const rows = node.querySelectorAll('.tt-row')
    const posValue = rows[0]?.querySelector('b')
    const negValue = rows[1]?.querySelector('b')
    expect(posValue?.classList.contains('tt-pos')).toBe(true)
    expect(negValue?.classList.contains('tt-neg')).toBe(true)
  })

  it('clears previous content on subsequent show()', () => {
    const tt = useHwTooltip()
    tt.show('First', [['A', '1']])
    tt.show('Second', [['B', '2']])
    const node = document.querySelector('.hw-tooltip')!
    expect(node.textContent).not.toContain('First')
    expect(node.textContent).not.toContain('A')
    expect(node.textContent).toContain('Second')
    expect(node.textContent).toContain('B')
  })

  it('hides the tooltip by removing the show class', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    let node = document.querySelector('.hw-tooltip')!
    expect(node.classList.contains('show')).toBe(true)
    tt.hide()
    node = document.querySelector('.hw-tooltip')!
    expect(node.classList.contains('show')).toBe(false)
  })

  it('positions tooltip to bottom-right of pointer by default', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement

    tt.move({ clientX: 100, clientY: 100 })
    const expectedX = 100 + 14
    const expectedY = 100 + 14
    expect(parseInt(node.style.left)).toBe(expectedX)
    expect(parseInt(node.style.top)).toBe(expectedY)
  })

  it('flips tooltip to left when right-edge exceeds window width', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement
    const w = node.offsetWidth

    const clientX = window.innerWidth - w / 2 - 10
    tt.move({ clientX, clientY: 100 })
    const left = parseInt(node.style.left)
    const expectedFlipped = clientX - w - 14
    expect(left).toBe(expectedFlipped)
  })

  it('flips tooltip upward when bottom-edge exceeds window height', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement
    const h = node.offsetHeight

    const clientY = window.innerHeight - h / 2 - 10
    tt.move({ clientX: 100, clientY })
    const top = parseInt(node.style.top)
    const expectedFlipped = clientY - h - 14
    expect(top).toBe(expectedFlipped)
  })

  it('clamps tooltip to stay within viewport bounds', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement

    // Position at top-left corner (would go off-screen without clamp)
    tt.move({ clientX: 2, clientY: 2 })
    const left = parseInt(node.style.left)
    const top = parseInt(node.style.top)
    // Should be clamped to 8px minimum margin
    expect(left).toBeGreaterThanOrEqual(8)
    expect(top).toBeGreaterThanOrEqual(8)
  })

  it('clamps tooltip at right and bottom edges', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement
    const w = node.offsetWidth
    const h = node.offsetHeight

    // Position at far right/bottom (would exceed bounds without clamp)
    tt.move({
      clientX: window.innerWidth - 5,
      clientY: window.innerHeight - 5,
    })
    const left = parseInt(node.style.left)
    const top = parseInt(node.style.top)
    expect(left + w + 8).toBeLessThanOrEqual(window.innerWidth)
    expect(top + h + 8).toBeLessThanOrEqual(window.innerHeight)
  })

  it('updates position on multiple move() calls', () => {
    const tt = useHwTooltip()
    tt.show('Test')
    const node = document.querySelector('.hw-tooltip') as HTMLDivElement

    tt.move({ clientX: 100, clientY: 100 })
    const x1 = parseInt(node.style.left)
    const y1 = parseInt(node.style.top)

    tt.move({ clientX: 200, clientY: 200 })
    const x2 = parseInt(node.style.left)
    const y2 = parseInt(node.style.top)

    expect(x2).toBeGreaterThan(x1)
    expect(y2).toBeGreaterThan(y1)
  })

  it('adds global pointerdown and scroll listeners on show() for touch devices', () => {
    const originalMatchMedia = window.matchMedia
    stubMatchMedia(true)

    try {
      const tt = useHwTooltip()
      const pointerDownSpy = vi.spyOn(document, 'addEventListener')
      const scrollSpy = vi.spyOn(window, 'addEventListener')

      tt.show('Test')

      expect(
        pointerDownSpy.mock.calls.some(
          (call) => call[0] === 'pointerdown',
        ),
      ).toBe(true)
      expect(
        scrollSpy.mock.calls.some((call) => call[0] === 'scroll'),
      ).toBe(true)

      pointerDownSpy.mockRestore()
      scrollSpy.mockRestore()
    } finally {
      window.matchMedia = originalMatchMedia
    }
  })

  it('removes global listeners on hide(force=true)', () => {
    const originalMatchMedia = window.matchMedia
    stubMatchMedia(true)

    try {
      const tt = useHwTooltip()
      tt.show('Test')

      const removeListenerSpy = vi.spyOn(document, 'removeEventListener')
      const removeScrollSpy = vi.spyOn(window, 'removeEventListener')

      tt.hide(true)

      expect(
        removeListenerSpy.mock.calls.some(
          (call) => call[0] === 'pointerdown',
        ),
      ).toBe(true)
      expect(
        removeScrollSpy.mock.calls.some((call) => call[0] === 'scroll'),
      ).toBe(true)

      removeListenerSpy.mockRestore()
      removeScrollSpy.mockRestore()
    } finally {
      window.matchMedia = originalMatchMedia
    }
  })

  it('respects tap-burst guard: unforced hide() does not remove listeners within TAP_BURST_MS on touch', () => {
    const originalMatchMedia = window.matchMedia
    stubMatchMedia(true)

    try {
      const tt = useHwTooltip()
      tt.show('Test')
      const node = document.querySelector('.hw-tooltip')! as HTMLDivElement
      expect(node.classList.contains('show')).toBe(true)

      // Unforced hide within burst window should not remove the show class
      tt.hide(false)
      expect(node.classList.contains('show')).toBe(true)

      tt.hide(true)
      expect(node.classList.contains('show')).toBe(false)
    } finally {
      window.matchMedia = originalMatchMedia
    }
  })

  it('does not add listeners on show() for hover-capable devices', () => {
    const originalMatchMedia = window.matchMedia
    stubMatchMedia(false) // Not a touch device

    try {
      const tt = useHwTooltip()
      const addListenerSpy = vi.spyOn(document, 'addEventListener')
      tt.show('Test')
      const hasPointerdown = addListenerSpy.mock.calls.some(
        (call) => call[0] === 'pointerdown',
      )
      expect(hasPointerdown).toBe(false)
      addListenerSpy.mockRestore()
    } finally {
      window.matchMedia = originalMatchMedia
    }
  })

  it('records shownAt timestamp on show()', () => {
    const originalMatchMedia = window.matchMedia
    stubMatchMedia(true)

    try {
      const tt = useHwTooltip()
      tt.show('Test2')
      const node = document.querySelector('.hw-tooltip')!
      tt.hide(false) // unforced hide should be guarded
      // Node should still have show class within TAP_BURST_MS
      expect(node.classList.contains('show')).toBe(true)
    } finally {
      window.matchMedia = originalMatchMedia
    }
  })

  it('reuses singleton node on multiple show() calls', () => {
    const tt = useHwTooltip()
    tt.show('First')
    const node1 = document.querySelector('.hw-tooltip')
    tt.show('Second')
    const node2 = document.querySelector('.hw-tooltip')
    expect(node1).toBe(node2)
  })

  it('handles empty rows array gracefully', () => {
    const tt = useHwTooltip()
    tt.show('Title', [])
    const node = document.querySelector('.hw-tooltip')!
    const rows = node.querySelectorAll('.tt-row')
    expect(rows).toHaveLength(0)
    const title = node.querySelector('.tt-title')
    expect(title?.textContent).toBe('Title')
  })

  it('handles rows with missing variant field (undefined)', () => {
    const tt = useHwTooltip()
    tt.show('Title', [['Label', 'Value']])
    const node = document.querySelector('.hw-tooltip')!
    const row = node.querySelector('.tt-row b')
    // Should not have any tt-* class when variant is undefined
    expect(row?.className).toBe('')
  })

  it('handles rows with empty strings', () => {
    const tt = useHwTooltip()
    tt.show('', [['', '']])
    const node = document.querySelector('.hw-tooltip')!
    const title = node.querySelector('.tt-title')
    const row = node.querySelector('.tt-row')
    expect(title?.textContent).toBe('')
    expect(row?.textContent).toBe('')
  })
})
