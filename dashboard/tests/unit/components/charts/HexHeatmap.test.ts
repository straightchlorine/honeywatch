import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HexHeatmap from '@/components/charts/HexHeatmap.vue'
import { seq } from '@/composables/useSeqScale'

/**
 * jsdom doesn't evaluate real CSS media queries, so the compact (<=900px)
 * breakpoint has to be forced per test rather than relying on an actual
 * viewport. Shape mirrors the global default in tests/setup.ts.
 */
function stubMatchMedia(matches: boolean): void {
  window.matchMedia = vi.fn((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  })) as unknown as typeof window.matchMedia
}

describe('HexHeatmap', () => {
  // Every test starts at full resolution unless it opts into compact mode,
  // so mode never leaks between tests regardless of run order.
  beforeEach(() => {
    stubMatchMedia(false)
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

  it('does not render hour-of-day tick labels across the top', () => {
    const w = mount(HexHeatmap, { props: { points: [{ weekday: 0, hour: 6, count: 5 }] } })
    const texts = w.findAll('svg text').map((t) => t.text())
    expect(texts).not.toContain('06')
    expect(texts).not.toContain('00')
    expect(texts).not.toContain('12')
    expect(texts).not.toContain('18')
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
  })
})
