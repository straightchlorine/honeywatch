import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import type { HeatmapPointResponse } from '@/api/generated/types.gen'
import HexHeatmap from '@/components/charts/HexHeatmap.vue'
import { seq } from '@/composables/useSeqScale'
import { stubMatchMedia } from '../../../setup'

// setup.ts's ResizeObserver is a no-op, so the component never measures. This one keeps its callback.
class FakeResizeObserver {
  static instances: FakeResizeObserver[] = []
  observed: Element[] = []
  disconnected = false
  callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
    FakeResizeObserver.instances.push(this)
  }
  observe(el: Element): void {
    this.observed.push(el)
  }
  disconnect(): void {
    this.disconnected = true
  }
}

describe('HexHeatmap', () => {
  // Every test starts at full resolution unless it opts into compact mode,
  // so mode never leaks between tests regardless of run order.
  beforeEach(() => {
    stubMatchMedia(false)
  })

  // Attached mounts are tracked so a failing assertion still removes them from document.body.
  const attached: { unmount: () => void }[] = []
  function mountAttached(props: { points: HeatmapPointResponse[] }) {
    const w = mount(HexHeatmap, { attachTo: document.body, props })
    attached.push(w)
    return w
  }
  afterEach(() => {
    for (const w of attached.splice(0)) w.unmount()
  })

  it('renders 168 hexagons and 7 weekday labels (Sun first)', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 0, count: 5 }] } })
    expect(w.findAll('polygon.hexcell')).toHaveLength(168)
    const days = w.findAll('svg text[text-anchor="end"]')
    expect(days).toHaveLength(7)
    expect(days[0]!.text()).toBe('Sun')
  })

  it('summarizes the busiest cell in the chart aria-label', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 2, hour: 14, count: 12 }] } })
    // graphics-document, not img/aria-hidden, so the focusable cells are legal.
    const label = w.find('[role="graphics-document"]').attributes('aria-label') ?? ''
    expect(label).toContain('Tue')
    expect(label).toContain('14:00')
    expect(label).toContain('12')
  })

  it('lists the hottest cells on the rail, ranked descending', () => {
    const w = mount(HexHeatmap, {
      props: {
        points: [
          { weekday: 1, hour: 9, count: 3 },
          { weekday: 3, hour: 18, count: 40 },
          { weekday: 5, hour: 20, count: 10 },
        ],
      },
    })
    const values = w.findAll('.hot-value').map((n) => n.text())
    expect(values).toEqual(['40', '10', '3'])
  })

  it('lists only populated cells in the offscreen fallback', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 1, hour: 9, count: 3 }] } })
    const items = w.findAll('.visually-hidden li')
    expect(items).toHaveLength(1)
    expect(items[0]!.text()).toContain('Mon')
  })

  it('reports no sessions when empty', () => {
    const w = mount(HexHeatmap, { props: { points: [] } })
    expect(w.text()).toContain('No sessions yet')
    expect(w.findAll('polygon.hexcell')).toHaveLength(0)
  })

  it('log-normalises the ramp across the populated range, not 0..max', () => {
    // Narrow band (240..5600) like real honeypot data: the ramp should
    // distinguish dimmest and brightest populated cells.
    const w = mount(HexHeatmap, {
      props: {
        points: [
          { weekday: 0, hour: 0, count: 240 },
          { weekday: 6, hour: 23, count: 5600 },
        ],
      },
    })
    const polys = w.findAll('polygon.hexcell')
    const dimmest = polys[0]!.attributes('fill') // weekday 0, hour 0 -> lo
    const brightest = polys[167]!.attributes('fill') // weekday 6, hour 23 -> hi
    expect(dimmest).not.toBe(brightest)
    expect(dimmest).toBe(seq(0.08))
    expect(brightest).toBe(seq(1))
  })

  it('fills a zero-count cell with var(--surface-2), not a ramp colour', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 0, count: 10 }] } })
    const polys = w.findAll('polygon.hexcell')
    const emptyCell = polys[1]!.attributes('fill') // weekday 0, hour 1 -> never populated
    expect(emptyCell).toBe('var(--surface-2)')
    expect(emptyCell).not.toBe(seq(0))
    expect(emptyCell).not.toBe(seq(1))
  })

  it('renders the hour axis below the last row, not across the top', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
    const ticks = w.findAll('svg text[text-anchor="middle"]')
    expect(ticks.map((t) => t.text())).toEqual(['00', '06', '12', '18'])
    const maxCy = Math.max(
      ...w.findAll('polygon.hexcell').map((p) => {
        const ys = (p.attributes('points') ?? '').split(' ').map((pt) => Number(pt.split(',')[1]))
        return (Math.min(...ys) + Math.max(...ys)) / 2
      }),
    )
    for (const t of ticks) expect(Number(t.attributes('y'))).toBeGreaterThan(maxCy)
  })

  it('is one Tab stop (the busiest cell) that arrows and Home/End move along the comb', async () => {
    const w = mountAttached({
      points: [
        { weekday: 2, hour: 5, count: 9 },
        { weekday: 4, hour: 20, count: 3 },
      ],
    })
    const stop = (): string[] =>
      w
        .findAll('polygon.hexcell')
        .flatMap((p, i) =>
          p.attributes('tabindex') === '0' ? [`${Math.floor(i / 24)}-${i % 24}`] : [],
        )
    // Cells are rendered row-major, so "w-h" is index w * 24 + h in the DOM.
    const cellNode = (key: string): Element => {
      const [wd, hr] = key.split('-').map(Number)
      return w.findAll('polygon.hexcell')[wd! * 24 + hr!]!.element
    }
    // The Tab stop and the real document focus must move together.
    const expectStop = (key: string): void => {
      expect(stop()).toEqual([key])
      expect(document.activeElement).toBe(cellNode(key))
    }
    expect(stop()).toEqual(['2-5']) // busiest; every other cell is tabindex -1
    const press = async (key: string, ctrlKey = false): Promise<void> => {
      const i = w.findAll('polygon.hexcell').findIndex((p) => p.attributes('tabindex') === '0')
      await w.findAll('polygon.hexcell')[i]!.trigger('keydown', { key, ctrlKey })
    }
    await press('ArrowRight')
    expectStop('2-6')
    await press('ArrowDown')
    expectStop('3-6')
    await press('End')
    expectStop('3-23')
    await press('ArrowRight') // clamps at the row end
    expectStop('3-23')
    await press('Home', true)
    expectStop('0-0')
    await press('End', true)
    expectStop('6-23')
  })

  it('shows the tooltip on keyboard focus and dismisses it on Escape without moving focus', async () => {
    const w = mountAttached({ points: [{ weekday: 2, hour: 5, count: 9 }] })
    const cell = w.find('polygon.hexcell[tabindex="0"]')
    // Real focus (not a synthetic focus event) so :focus-visible and activeElement behave as in a browser.
    ;(cell.element as SVGElement).focus()
    await nextTick()
    const tip = document.querySelector('.hw-tooltip')!
    // The focus ring is not asserted: jsdom's :focus-visible flips with earlier events in this file.
    expect(document.activeElement).toBe(cell.element)
    expect(tip.classList.contains('show')).toBe(true)
    expect(tip.textContent).toContain('Tue 05:00-05:59')
    await cell.trigger('keydown', { key: 'Escape' })
    expect(tip.classList.contains('show')).toBe(false)
    expect(document.activeElement).toBe(cell.element)
  })

  it('states the grain beside the Busiest times heading', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
    expect(w.find('#hot-cells-title').text()).toContain('by hour')
    stubMatchMedia(true)
    const c = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
    expect(c.find('#hot-cells-title').text()).toContain('3-hour bands')
  })

  it('produces finite fills when every populated count is equal', () => {
    const w = mount(HexHeatmap, {
      props: {
        points: [
          { weekday: 0, hour: 0, count: 50 },
          { weekday: 1, hour: 1, count: 50 },
        ],
      },
    })
    const fills = w.findAll('polygon.hexcell').map((p) => p.attributes('fill') ?? '')
    expect(fills.some((f) => f.includes('NaN'))).toBe(false)
    expect(fills.some((f) => f.includes('Infinity'))).toBe(false)
  })

  describe('compact mode (<=900px hour binning)', () => {
    it('keeps 7 x 24 = 168 hexcell polygons at full resolution', () => {
      stubMatchMedia(false)
      const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 0, count: 5 }] } })
      expect(w.findAll('polygon.hexcell')).toHaveLength(7 * 24)
    })

    it('bins hours 3-wide into 7 x 8 = 56 hexcell polygons when compact', () => {
      stubMatchMedia(true)
      const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 0, count: 5 }] } })
      expect(w.findAll('polygon.hexcell')).toHaveLength(7 * 8)
    })

    it('labels a compact bin with its 3-hour range and sums the source hours', () => {
      stubMatchMedia(true)
      const w = mount(HexHeatmap, {
        props: {
          points: [
            { weekday: 0, hour: 18, count: 3 },
            { weekday: 0, hour: 19, count: 5 },
            { weekday: 0, hour: 20, count: 2 },
          ],
        },
      })
      const bin = w
        .findAll('polygon.hexcell')
        .find((p) => (p.attributes('aria-label') ?? '').includes('18:00-20:59'))
      expect(bin).toBeTruthy()
      expect(bin!.attributes('aria-label')).toBe('Sun 18:00-20:59: 10 sessions')
    })

    it('sizes the offscreen SR list to the populated cell count in the active mode', () => {
      stubMatchMedia(true)
      const w = mount(HexHeatmap, {
        props: {
          points: [
            { weekday: 0, hour: 0, count: 2 },
            { weekday: 0, hour: 1, count: 3 }, // same compact bin as hour 0 (00:00-02:59)
            { weekday: 0, hour: 10, count: 4 }, // a different bin (09:00-11:59)
          ],
        },
      })
      const items = w.findAll('.visually-hidden li')
      expect(items).toHaveLength(2)
      expect(items[0]!.text()).toContain('Sun 00:00-02:59 UTC: 5 sessions')
      expect(items[1]!.text()).toContain('Sun 09:00-11:59 UTC: 4 sessions')
    })

    it('places the 06 hour tick on its 3-hour bin when compact', () => {
      stubMatchMedia(true)
      const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
      // Compact axisTicks: GUT 26, bin index 6 / 3 = 2, x = GUT + HXW * 2 + HXW / 2.
      const HXW = Math.sqrt(3) * 12
      const tick = w.findAll('svg text[text-anchor="middle"]').find((t) => t.text() === '06')!
      expect(Number(tick.attributes('x'))).toBeCloseTo(26 + HXW * 2.5)
    })
  })

  describe('label scaling', () => {
    beforeEach(() => {
      FakeResizeObserver.instances = []
      vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    })
    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('rescales day labels and the hour axis to the measured width, and disconnects on unmount', async () => {
      const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
      const svg = w.find('svg').element
      const ro = FakeResizeObserver.instances.find((o) => o.observed.includes(svg))!
      expect(ro).toBeTruthy()
      const dayLabel = (): Element => w.findAll('svg text[text-anchor="end"]')[0]!.element
      // Hour tick '06' y; the comb bottom is 138 units (TOP + 9R + 2R with R = 12) and the axis sits 1.15 label units below it.
      const axisTick = (): number =>
        Number(
          w
            .findAll('svg text[text-anchor="middle"]')
            .find((t) => t.text() === '06')!
            .attributes('y'),
        )
      // Without a measurement, labels stay at 12 units.
      expect(dayLabel().getAttribute('font-size')).toBe('12')
      expect(axisTick()).toBeCloseTo(138 + 1.15 * 12)

      // viewBox is "0 0 VW VH"; reporting twice VW as the CSS width halves every unit label.
      const vw = Number(w.find('svg').attributes('viewBox')!.split(' ')[2])
      const entry = { contentRect: { width: vw * 2 } } as unknown as ResizeObserverEntry
      ro.callback([entry], ro as unknown as ResizeObserver)
      await nextTick()
      expect(Number(dayLabel().getAttribute('font-size'))).toBeCloseTo(6)
      expect(axisTick()).toBeCloseTo(138 + 1.15 * 6)

      w.unmount()
      expect(ro.disconnected).toBe(true)
    })
  })
})
