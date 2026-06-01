import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ActivityHeatmap from '@/components/charts/ActivityHeatmap.vue'

describe('ActivityHeatmap', () => {
  it('renders 168 cells and 7 weekday labels (Sun first)', () => {
    const w = mount(ActivityHeatmap, { props: { points: [{ weekday: 0, hour: 0, count: 5 }] } })
    expect(w.findAll('.cell')).toHaveLength(168)
    const days = w.findAll('.day-label')
    expect(days).toHaveLength(7)
    expect(days[0]!.text()).toBe('Sun')
  })

  it('summarizes the busiest cell in the role=img aria-label', () => {
    const w = mount(ActivityHeatmap, { props: { points: [{ weekday: 2, hour: 14, count: 12 }] } })
    const label = w.find('figure').attributes('aria-label') ?? ''
    expect(label).toContain('Tue')
    expect(label).toContain('14:00')
    expect(label).toContain('12')
  })

  it('lists only populated cells in the offscreen fallback', () => {
    const w = mount(ActivityHeatmap, { props: { points: [{ weekday: 1, hour: 9, count: 3 }] } })
    const items = w.findAll('.visually-hidden li')
    expect(items).toHaveLength(1)
    expect(items[0]!.text()).toContain('Mon')
  })

  it('reports no sessions when empty', () => {
    const w = mount(ActivityHeatmap, { props: { points: [] } })
    expect(w.find('figure').attributes('aria-label')).toContain('No sessions')
    expect(w.findAll('.visually-hidden li')).toHaveLength(0)
  })
})
