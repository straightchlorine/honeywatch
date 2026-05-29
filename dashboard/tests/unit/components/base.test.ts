import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Stat from '@/components/base/Stat.vue'
import BarList from '@/components/base/BarList.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Card from '@/components/base/Card.vue'
import PageHeader from '@/components/base/PageHeader.vue'
import Spinner from '@/components/base/Spinner.vue'
import LoadingState from '@/components/base/LoadingState.vue'

describe('Stat', () => {
  it('shows an up arrow + visually-hidden "increase" for an up trend', () => {
    const w = mount(Stat, { props: { value: 10, label: 'X', trend: 'up', delta: '+5' } })
    expect(w.text()).toContain('▲')
    expect(w.text()).toContain('increase')
    expect(w.get('.stat-delta').classes()).toContain('trend-up')
  })

  it('shows a down arrow + "decrease" for a down trend', () => {
    const w = mount(Stat, { props: { value: 10, label: 'X', trend: 'down', delta: '-5' } })
    expect(w.text()).toContain('▼')
    expect(w.text()).toContain('decrease')
    expect(w.get('.stat-delta').classes()).toContain('trend-down')
  })

  it('renders no trend symbol when trend is absent', () => {
    const w = mount(Stat, { props: { value: 10, label: 'X' } })
    expect(w.text()).not.toContain('▲')
    expect(w.text()).not.toContain('▼')
  })
})

describe('BarList', () => {
  it('renders rows with formatted counts and the list aria-label', () => {
    const items = [{ key: 'a', label: 'root', count: 1234, widthPct: '50%' }]
    const w = mount(BarList, { props: { items, label: 'Top' } })
    expect(w.findAll('li')).toHaveLength(1)
    expect(w.text()).toContain('1,234')
    expect(w.get('ul').attributes('aria-label')).toBe('Top')
  })

  it('renders an EmptyState with the empty text when there are no items', () => {
    const w = mount(BarList, { props: { items: [], label: 'Top', emptyText: 'none yet' } })
    expect(w.find('ul').exists()).toBe(false)
    expect(w.text()).toContain('none yet')
  })
})

describe('EmptyState', () => {
  it('defaults to an h2 heading', () => {
    expect(mount(EmptyState, { props: { title: 'Empty' } }).find('h2').exists()).toBe(true)
  })

  it('honors headingLevel and renders the hint', () => {
    const w = mount(EmptyState, { props: { title: 'E', headingLevel: 3, hint: 'try later' } })
    expect(w.find('h3').exists()).toBe(true)
    expect(w.text()).toContain('try later')
  })
})

describe('Card', () => {
  it('renders the title prop as an h2 by default', () => {
    expect(mount(Card, { props: { title: 'T' } }).find('h2.card-title').exists()).toBe(true)
  })

  it('honors headingLevel', () => {
    expect(
      mount(Card, { props: { title: 'T', headingLevel: 3 } }).find('h3.card-title').exists(),
    ).toBe(true)
  })

  it('lets the title slot override the default heading', () => {
    const w = mount(Card, {
      props: { title: 'T' },
      slots: { title: '<span class="custom">X</span>' },
    })
    expect(w.find('.custom').exists()).toBe(true)
    expect(w.find('h2.card-title').exists()).toBe(false)
  })

  it('applies the padding class', () => {
    expect(mount(Card, { props: { padding: 'lg' } }).find('.pad-lg').exists()).toBe(true)
  })
})

describe('PageHeader', () => {
  it('renders an h1 title and an optional sub', () => {
    const w = mount(PageHeader, { props: { title: 'Overview', sub: 'desc' } })
    expect(w.get('h1').text()).toBe('Overview')
    expect(w.text()).toContain('desc')
  })

  it('omits the sub when not provided', () => {
    expect(mount(PageHeader, { props: { title: 'X' } }).find('.page-sub').exists()).toBe(false)
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
