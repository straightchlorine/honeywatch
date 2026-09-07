import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EmptyState from '@/components/base/EmptyState.vue'
import Spinner from '@/components/base/Spinner.vue'
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



describe('Spinner', () => {
  it('exposes a status role with a hidden label by default', () => {
    const w = mount(Spinner)
    expect(w.get('span').attributes('role')).toBe('status')
    expect(w.text()).toContain('Loading')
  })

  it('is aria-hidden with no role when decorative', () => {
    const w = mount(Spinner, { props: { decorative: true } })
    expect(w.get('span').attributes('aria-hidden')).toBe('true')
    expect(w.get('span').attributes('role')).toBeUndefined()
  })
})

describe('LoadingState', () => {
  it('is a polite status region with a label', () => {
    const w = mount(LoadingState, { props: { label: 'Loading data' } })
    expect(w.get('.loading').attributes('role')).toBe('status')
    expect(w.get('.loading').attributes('aria-live')).toBe('polite')
    expect(w.text()).toContain('Loading data')
  })
})
