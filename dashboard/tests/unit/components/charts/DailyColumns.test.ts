import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DailyColumns from '@/components/charts/DailyColumns.vue'

describe('DailyColumns', () => {
  it('renders one bar per bucket with a peak summary', () => {
    const w = mount(DailyColumns, {
      props: {
        buckets: [
          { bucket: '2026-05-29T00:00:00+00:00', count: 4 },
          { bucket: '2026-05-30T00:00:00+00:00', count: 9 },
        ],
      },
    })
    expect(w.findAll('rect.daily-bar')).toHaveLength(2)
    const label = w.find('figure').attributes('aria-label') ?? ''
    expect(label).toContain('Peak')
    expect(label).toContain('9')
  })

  it('labels the peak bar with its count directly on the chart', () => {
    const w = mount(DailyColumns, {
      props: {
        buckets: [
          { bucket: '2026-05-29T00:00:00+00:00', count: 4 },
          { bucket: '2026-05-30T00:00:00+00:00', count: 9 },
        ],
      },
    })
    const bars = w.findAll('rect.daily-bar')
    expect(bars[1]!.attributes('fill')).toBe('var(--accent)')
    expect(bars[0]!.attributes('fill')).toBe('var(--series-1)')
  })

  it('shows an empty state when there are no buckets', () => {
    const w = mount(DailyColumns, { props: { buckets: [] } })
    expect(w.find('figure').exists()).toBe(false)
    expect(w.text()).toContain('No activity yet')
  })

  it('densifies buckets with multi-day gaps, rendering slots for missing days', () => {
    // Input: 10 buckets spanning Jul 1-5 and Jul 26-30 (21-day gap in the middle)
    const gappyBuckets = [
      { bucket: '2026-07-01T00:00:00+00:00', count: 5 },
      { bucket: '2026-07-02T00:00:00+00:00', count: 3 },
      { bucket: '2026-07-03T00:00:00+00:00', count: 7 },
      { bucket: '2026-07-04T00:00:00+00:00', count: 2 },
      { bucket: '2026-07-05T00:00:00+00:00', count: 4 },
      { bucket: '2026-07-26T00:00:00+00:00', count: 1 },
      { bucket: '2026-07-27T00:00:00+00:00', count: 8 },
      { bucket: '2026-07-28T00:00:00+00:00', count: 6 },
      { bucket: '2026-07-29T00:00:00+00:00', count: 2 },
      { bucket: '2026-07-30T00:00:00+00:00', count: 9 },
    ]
    const w = mount(DailyColumns, { props: { buckets: gappyBuckets } })

    // After densification, should render 30 bars (Jul 1-30 inclusive),
    // not 10. The missing days (6-25) fill with count 0.
    const bars = w.findAll('rect.daily-bar')
    expect(bars).toHaveLength(30)

    const dateLabels = w.findAll('text')
    const lastDateLabel = dateLabels.find(
      (t) => t.text() === 'Jul 30'
    )
    expect(lastDateLabel).toBeDefined()
  })

  it('clamps axis and marks clipped bars when there is a genuine outlier', () => {
    // 29 days at ~1000, one spike at 11533. This is a real case.
    const buckets: Array<{ bucket: string; count: number }> = []
    for (let i = 1; i <= 29; i++) {
      buckets.push({
        bucket: `2026-08-${String(i).padStart(2, '0')}T00:00:00+00:00`,
        count: 1000 + Math.floor(Math.random() * 200) - 100, // 900-1100
      })
    }
    buckets.push({
      bucket: '2026-08-30T00:00:00+00:00',
      count: 11533,
    })

    const w = mount(DailyColumns, { props: { buckets } })

    const axisCapNote = w.findAll('text').find((t) => t.text() === 'axis capped')
    expect(axisCapNote).toBeDefined()

    // Value labels have font-weight="600" to distinguish from gridline labels
    const valueLabels = w.findAll('text[font-weight="600"]')
    expect(valueLabels.length).toBe(1)

    const bars = w.findAll('rect.daily-bar')
    expect(bars.length).toBe(30)

    // The last bar (spike) should reach full plot height
    const spikeBar = bars[29]!
    const plotHeight = 168 - 12 - 22 // H - PLOT_T - 22
    expect(Math.abs(parseFloat(spikeBar.attributes('height') ?? '0') - plotHeight)).toBeLessThan(1)

    // A typical bar should be at least 25% of plot height after clamping
    const typicalBar = bars[0]!
    const typicalHeight = parseFloat(typicalBar.attributes('height') ?? '0')
    expect(typicalHeight).toBeGreaterThan(plotHeight * 0.25)

    const label = w.find('figure').attributes('aria-label') ?? ''
    expect(label).toContain('Axis capped')
    expect(label).toContain('11')
  })

  it('does not clamp when all values are similar', () => {
    // All 30 days have counts between 1000 and 1100 (similar range)
    const buckets: Array<{ bucket: string; count: number }> = []
    for (let i = 1; i <= 30; i++) {
      buckets.push({
        bucket: `2026-08-${String(i).padStart(2, '0')}T00:00:00+00:00`,
        count: 1000 + Math.floor(Math.random() * 100),
      })
    }

    const w = mount(DailyColumns, { props: { buckets } })

    const axisCapNote = w.findAll('text').find((t) => t.text() === 'axis capped')
    expect(axisCapNote).toBeUndefined()

    const valueLabels = w.findAll('text[font-weight="600"]')
    expect(valueLabels.length).toBe(1)

    const bars = w.findAll('rect.daily-bar')
    const plotHeight = 168 - 12 - 22
    const maxBarHeight = Math.max(...bars.map((b) => parseFloat(b.attributes('height') ?? '0')))
    expect(maxBarHeight).toBeLessThan(plotHeight)

    const label = w.find('figure').attributes('aria-label') ?? ''
    expect(label).not.toContain('Axis capped')
  })
})
