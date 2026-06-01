import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ActivityTimeline from '@/components/charts/ActivityTimeline.vue'

describe('ActivityTimeline', () => {
  it('renders one bar per bucket with a peak summary', () => {
    const w = mount(ActivityTimeline, {
      props: {
        label: 'Daily session counts',
        buckets: [
          { bucket: '2026-05-29T00:00:00+00:00', count: 4 },
          { bucket: '2026-05-30T00:00:00+00:00', count: 9 },
        ],
      },
    })
    expect(w.findAll('.bar')).toHaveLength(2)
    const label = w.find('figure').attributes('aria-label') ?? ''
    expect(label).toContain('Peak')
    expect(label).toContain('9')
  })

  it('floors non-zero bars to a visible height and scales the max to 100%', () => {
    const w = mount(ActivityTimeline, {
      props: {
        label: 'x',
        buckets: [
          { bucket: '2026-05-29T00:00:00+00:00', count: 1 },
          { bucket: '2026-05-30T00:00:00+00:00', count: 100 },
        ],
      },
    })
    const bars = w.findAll('.bar')
    expect((bars[0]!.element as HTMLElement).style.height).toBe('2%')
    expect((bars[1]!.element as HTMLElement).style.height).toBe('100%')
  })

  it('shows an empty state when there are no buckets', () => {
    const w = mount(ActivityTimeline, { props: { label: 'x', buckets: [] } })
    expect(w.find('.timeline').exists()).toBe(false)
    expect(w.text()).toContain('No activity yet')
  })
})
