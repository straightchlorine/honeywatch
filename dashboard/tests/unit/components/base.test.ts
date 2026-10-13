import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EmptyState from '@/components/base/EmptyState.vue'
import LoadingState from '@/components/base/LoadingState.vue'
import SeqLegend from '@/components/base/SeqLegend.vue'

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

  it('renders an h1 when headingLevel is 1', () => {
    expect(
      mount(EmptyState, { props: { title: 'E', headingLevel: 1 } })
        .find('h1')
        .exists(),
    ).toBe(true)
  })

  it('renders the icon slot after the icon prop', () => {
    const w = mount(EmptyState, {
      props: { title: 'E', icon: 'o' },
      slots: { icon: '<span class="custom-icon">+</span>' },
    })
    const kids = w.findAll('.empty > *')
    expect(kids[0]!.classes()).toContain('empty-icon')
    expect(kids[1]!.classes()).toContain('custom-icon')
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

describe('SeqLegend', () => {
  it('renders the title span before the min label', () => {
    const w = mount(SeqLegend, { props: { min: '0', max: '9', title: 'Hits' } })
    const title = w.get('.title')
    expect(title.text()).toBe('Hits')
    expect(w.element.firstElementChild).toBe(title.element)
    expect(w.findAll('span')[1]!.text()).toBe('0')
  })

  it('renders no title span when the title is absent', () => {
    const w = mount(SeqLegend, { props: { min: '0', max: '9' } })
    expect(w.find('.title').exists()).toBe(false)
  })
})
