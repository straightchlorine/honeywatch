import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'

import { useRovingGrid } from '@/composables/useRovingGrid'

interface Cell {
  key: string
  x: number
}

type Api = ReturnType<typeof useRovingGrid<Cell>>

const COLS = 4

function cellsOf(n: number): Cell[] {
  return Array.from({ length: n }, (_, i) => ({ key: `k${i}`, x: i }))
}

/** Renders the cells as role=button rects in one svg, wired the way the charts wire them. */
function mountGrid(initial: Cell[], opts: { cols?: number; activate?: (c: Cell) => void } = {}) {
  const host = document.createElement('div')
  host.setAttribute('data-test-host', '')
  document.body.appendChild(host)
  const cells = ref(initial)
  const cols = opts.cols ?? COLS
  let api!: Api
  const Harness = defineComponent({
    setup() {
      api = useRovingGrid<Cell>({
        cells,
        cols: () => cols,
        home: 'k0',
        geom: (c) => ({ cx: c.x, cy: 10, r: 5 }),
        tip: (c) => [c.key, [['x', String(c.x)]]],
        ...(opts.activate && { activate: opts.activate }),
      })
      return () =>
        h(
          'svg',
          null,
          cells.value.map((c) =>
            h('rect', {
              key: c.key,
              role: 'button',
              tabindex: api.tabKey.value === c.key ? 0 : -1,
              'data-key': c.key,
              onFocus: (e: FocusEvent) => api.onFocus(c, e),
              onBlur: () => api.onBlur(),
              onKeydown: (e: KeyboardEvent) => api.onKeydown(c, e),
            }),
          ),
        )
    },
  })
  const wrapper = mount(Harness, { attachTo: host })
  return { host, api, cells, wrapper }
}

/** Keys of the elements carrying tabindex=0; the grid should have exactly one. */
function stops(host: HTMLElement): string[] {
  return Array.from(
    host.querySelectorAll('[tabindex="0"]'),
    (el) => el.getAttribute('data-key') ?? '',
  )
}

async function focusCell(host: HTMLElement, key: string): Promise<void> {
  host.querySelector(`[data-key="${key}"]`)!.dispatchEvent(new FocusEvent('focus'))
  await nextTick()
}

async function blurCell(host: HTMLElement, key: string): Promise<void> {
  host.querySelector(`[data-key="${key}"]`)!.dispatchEvent(new FocusEvent('blur'))
  await nextTick()
}

async function press(
  host: HTMLElement,
  from: string,
  key: string,
  init: KeyboardEventInit = {},
): Promise<KeyboardEvent> {
  const ev = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init })
  host.querySelector(`[data-key="${from}"]`)!.dispatchEvent(ev)
  await nextTick()
  return ev
}

/** Stubs `:focus-visible` only; every other selector still goes through the real matcher. */
function stubFocusVisible(result: boolean | 'throw') {
  const original = Element.prototype.matches
  return vi.spyOn(Element.prototype, 'matches').mockImplementation(function (
    this: Element,
    selector: string,
  ) {
    if (selector !== ':focus-visible') return original.call(this, selector)
    if (result === 'throw') throw new SyntaxError(`'${selector}' is not a valid selector`)
    return result
  })
}

function tooltipShown(): boolean {
  return document.querySelector('.hw-tooltip')?.classList.contains('show') ?? false
}

afterEach(() => {
  document.querySelectorAll('[data-test-host]').forEach((n) => n.remove())
  document.querySelector('.hw-tooltip')?.classList.remove('show')
  vi.restoreAllMocks()
})

describe('useRovingGrid', () => {
  describe('tab stop', () => {
    it('is exactly one cell, home, before any focus', () => {
      const { host, api } = mountGrid(cellsOf(12))
      expect(stops(host)).toEqual(['k0'])
      expect(api.tabKey.value).toBe('k0')
    })

    it('moves to the focused cell', async () => {
      const { host, api } = mountGrid(cellsOf(12))
      await focusCell(host, 'k6')
      expect(stops(host)).toEqual(['k6'])
      expect(api.tabKey.value).toBe('k6')
    })

    it('falls back to home when the focused cell leaves the list', async () => {
      const { host, cells } = mountGrid(cellsOf(12))
      await focusCell(host, 'k6')
      cells.value = cellsOf(12).filter((c) => c.key !== 'k6')
      await nextTick()
      expect(stops(host)).toEqual(['k0'])
    })

    it('falls back to home on an empty grid', () => {
      const { host, api } = mountGrid([])
      expect(host.querySelectorAll('[role="button"]')).toHaveLength(0)
      expect(api.tabKey.value).toBe('k0')
    })
  })

  describe('arrow keys', () => {
    it.each([
      ['ArrowRight', 'k5', 'k6'],
      ['ArrowLeft', 'k5', 'k4'],
      ['ArrowDown', 'k5', 'k9'],
      ['ArrowUp', 'k5', 'k1'],
    ])('%s from %s moves to %s', async (key, from, to) => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, from)
      await press(host, from, key)
      expect(stops(host)).toEqual([to])
    })

    it.each([
      ['ArrowLeft', 'k4'],
      ['ArrowRight', 'k3'],
      ['ArrowUp', 'k2'],
      ['ArrowDown', 'k9'],
      ['ArrowDown', 'k8'],
    ])('%s from %s clamps at the edge', async (key, from) => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, from)
      await press(host, from, key)
      expect(stops(host)).toEqual([from])
    })

    it('moves DOM focus to the target cell', async () => {
      const { host } = mountGrid(cellsOf(12))
      host.querySelector<SVGElement>('[data-key="k5"]')!.focus()
      await nextTick()
      await press(host, 'k5', 'ArrowRight')
      expect(document.activeElement?.getAttribute('data-key')).toBe('k6')
    })

    it('calls preventDefault on handled keys', async () => {
      const { host } = mountGrid(cellsOf(12))
      const ev = await press(host, 'k5', 'ArrowRight')
      expect(ev.defaultPrevented).toBe(true)
    })

    it('ignores keys it does not handle', async () => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      const ev = await press(host, 'k5', 'a')
      expect(stops(host)).toEqual(['k5'])
      expect(ev.defaultPrevented).toBe(false)
    })
  })

  describe('Home and End', () => {
    it.each([
      ['Home', 'k6', 'k4'],
      ['End', 'k5', 'k7'],
    ])('%s from %s stays on its row (%s)', async (key, from, to) => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, from)
      await press(host, from, key)
      expect(stops(host)).toEqual([to])
    })

    it.each([
      ['Home', 'k6', 'k0'],
      ['End', 'k5', 'k11'],
    ])('Ctrl+%s from %s goes to the grid edge (%s)', async (key, from, to) => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, from)
      await press(host, from, key, { ctrlKey: true })
      expect(stops(host)).toEqual([to])
    })
  })

  describe('partial last row', () => {
    // 10 cells in 4 columns: the last row holds k8 and k9 only.
    it('End on the last row stops at the final cell', async () => {
      const { host } = mountGrid(cellsOf(10))
      await focusCell(host, 'k8')
      await press(host, 'k8', 'End')
      expect(stops(host)).toEqual(['k9'])
    })

    it('ArrowRight on the final cell stays put', async () => {
      const { host } = mountGrid(cellsOf(10))
      await focusCell(host, 'k9')
      await press(host, 'k9', 'ArrowRight')
      expect(stops(host)).toEqual(['k9'])
    })

    it('ArrowDown past the last cell stays put', async () => {
      const { host } = mountGrid(cellsOf(10))
      await focusCell(host, 'k6')
      await press(host, 'k6', 'ArrowDown')
      expect(stops(host)).toEqual(['k6'])
    })
  })

  describe('shrinking list', () => {
    it('keeps navigation in range after the grid shrinks', async () => {
      const { host, cells } = mountGrid(cellsOf(12))
      await focusCell(host, 'k3')
      cells.value = cellsOf(6)
      await nextTick()
      await press(host, 'k3', 'ArrowDown')
      expect(stops(host)).toEqual(['k3'])
    })
  })

  describe('modifier keys', () => {
    it.each(['altKey', 'metaKey'] as const)('ignores ArrowRight with %s', async (mod) => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, 'k1')
      const ev = await press(host, 'k1', 'ArrowRight', { [mod]: true })
      expect(stops(host)).toEqual(['k1'])
      expect(ev.defaultPrevented).toBe(false)
    })

    it.each(['altKey', 'metaKey', 'ctrlKey'] as const)(
      'ignores Enter with %s and does not activate',
      async (mod) => {
        const activate = vi.fn()
        const { host } = mountGrid(cellsOf(12), { activate })
        const ev = await press(host, 'k2', 'Enter', { [mod]: true })
        expect(activate).not.toHaveBeenCalled()
        expect(ev.defaultPrevented).toBe(false)
      },
    )
  })

  describe('activation', () => {
    it.each([
      ['Enter', 'Enter'],
      ['Space', ' '],
    ])('%s calls activate with the cell', async (_name, key) => {
      const activate = vi.fn()
      const { host } = mountGrid(cellsOf(12), { activate })
      const ev = await press(host, 'k2', key)
      expect(activate).toHaveBeenCalledWith(expect.objectContaining({ key: 'k2' }))
      expect(ev.defaultPrevented).toBe(true)
    })

    it('shows the tooltip on Enter when no activate is given', async () => {
      const { host } = mountGrid(cellsOf(12))
      await press(host, 'k2', 'Enter')
      expect(tooltipShown()).toBe(true)
    })
  })

  describe('focus ring', () => {
    it('is the cell geometry under :focus-visible', async () => {
      stubFocusVisible(true)
      const { host, api } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(api.ring.value).toEqual({ cx: 5, cy: 10, r: 5 })
    })

    it('is null for pointer focus', async () => {
      stubFocusVisible(false)
      const { host, api } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(api.ring.value).toBe(null)
    })

    it('is shown when :focus-visible is unsupported', async () => {
      stubFocusVisible('throw')
      const { host, api } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(api.ring.value).toEqual({ cx: 5, cy: 10, r: 5 })
    })

    it('clears on blur', async () => {
      stubFocusVisible(true)
      const { host, api } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(api.ring.value).not.toBe(null)
      await blurCell(host, 'k5')
      expect(api.ring.value).toBe(null)
    })

    it('clears when the focused cell leaves the list', async () => {
      stubFocusVisible(true)
      const { host, api, cells } = mountGrid(cellsOf(12))
      await focusCell(host, 'k6')
      cells.value = cellsOf(12).filter((c) => c.key !== 'k6')
      await nextTick()
      expect(api.ring.value).toBe(null)
    })
  })

  describe('tooltip', () => {
    it('shows on focus', async () => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(tooltipShown()).toBe(true)
    })

    it('hides on blur', async () => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      await blurCell(host, 'k5')
      expect(tooltipShown()).toBe(false)
    })

    it('hides on Escape', async () => {
      const { host } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      await press(host, 'k5', 'Escape')
      expect(tooltipShown()).toBe(false)
    })

    it('hides when the grid unmounts with a focused cell', async () => {
      const { host, wrapper } = mountGrid(cellsOf(12))
      await focusCell(host, 'k5')
      expect(tooltipShown()).toBe(true)
      wrapper.unmount()
      expect(tooltipShown()).toBe(false)
    })
  })
})
