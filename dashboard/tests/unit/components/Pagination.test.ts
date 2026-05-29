import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Pagination from '@/components/base/Pagination.vue'

describe('Pagination', () => {
  it('renders page info, including the optional total', () => {
    const w = mount(Pagination, { props: { page: 2, pages: 5, total: 97 } })
    expect(w.text()).toContain('Page 2 of 5')
    expect(w.text()).toContain('97 total')
  })

  it('omits the total when not provided', () => {
    const w = mount(Pagination, { props: { page: 1, pages: 3 } })
    expect(w.text()).toContain('Page 1 of 3')
    expect(w.text()).not.toContain('total')
  })

  it('disables prev on the first page and next on the last', () => {
    const first = mount(Pagination, { props: { page: 1, pages: 3 } })
    expect(first.get('[aria-label="Previous page"]').attributes('disabled')).toBeDefined()
    expect(first.get('[aria-label="Next page"]').attributes('disabled')).toBeUndefined()

    const last = mount(Pagination, { props: { page: 3, pages: 3 } })
    expect(last.get('[aria-label="Next page"]').attributes('disabled')).toBeDefined()
  })

  it('emits the clamped target page on prev/next within bounds', async () => {
    const w = mount(Pagination, { props: { page: 2, pages: 3 } })
    await w.get('[aria-label="Next page"]').trigger('click')
    await w.get('[aria-label="Previous page"]').trigger('click')
    expect(w.emitted('update:page')).toEqual([[3], [1]])
  })

  it('does not emit past the bounds', async () => {
    const w = mount(Pagination, { props: { page: 1, pages: 1 } })
    await w.get('[aria-label="Previous page"]').trigger('click')
    await w.get('[aria-label="Next page"]').trigger('click')
    expect(w.emitted('update:page')).toBeUndefined()
  })
})
