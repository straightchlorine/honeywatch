import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'

describe('EmptyState', () => {
  it('defaults to an h2 heading', () => {
    expect(
      mount(EmptyState, { props: { title: 'Empty' } })
        .find('h2')
        .exists(),
    ).toBe(true)
  })

  it('honors headingLevel and renders the hint', () => {
    const w = mount(EmptyState, { props: { title: 'E', headingLevel: 3, hint: 'try later' } })
    expect(w.find('h3').exists()).toBe(true)
    expect(w.text()).toContain('try later')
  })
})

describe('LoadingState', () => {
  it('is a status region with a hidden label and a decorative mark', () => {
    const w = mount(LoadingState)
    expect(w.get('.loading').attributes('role')).toBe('status')
    expect(w.get('.visually-hidden').text()).toBe('Loading')
    expect(w.get('svg').attributes('aria-hidden')).toBe('true')
  })
})
