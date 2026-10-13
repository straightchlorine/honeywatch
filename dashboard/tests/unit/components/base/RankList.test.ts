import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import RankList, { type RankRow } from '@/components/base/RankList.vue'

const rows: RankRow[] = [
  { label: 'China', value: '34,468', frac: 1, title: 'China, in full' },
  { label: 'United States', value: '12,004', frac: 0.35 },
]

describe('RankList', () => {
  it('renders rows that share a label without duplicate keys', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const dupes: RankRow[] = [
      { label: '<ip>', value: '5', frac: 1 },
      { label: '<ip>', value: '3', frac: 0.6 },
    ]
    const w = mount(RankList, { props: { rows: dupes } })
    expect(w.findAll('.rank-row')).toHaveLength(2)
    expect(warn.mock.calls.flat().join(' ')).not.toMatch(/Duplicate keys/)
    warn.mockRestore()
  })

  it('renders one row per entry', () => {
    const w = mount(RankList, { props: { rows } })
    expect(w.findAll('.rank-row')).toHaveLength(2)
  })

  it('keeps rows out of the tab order; the list is the single stop only while it overflows', () => {
    const w = mount(RankList, { props: { rows } })
    for (const el of w.findAll('.rank-row')) expect(el.attributes('tabindex')).toBeUndefined()
    // jsdom has no layout, so nothing overflows
    expect(w.find('.rank-list').attributes('tabindex')).toBeUndefined()
  })

  it('gives the scroller no role or name while it does not overflow', () => {
    const w = mount(RankList, { props: { rows, label: 'Origins by country' } })
    const el = w.find('.rank-list')
    expect(el.attributes('role')).toBeUndefined()
    expect(el.attributes('aria-label')).toBeUndefined()
  })

  it('renders the badge column only when at least one row has a badge', () => {
    const withoutBadge = mount(RankList, { props: { rows } })
    expect(withoutBadge.find('.rk-badge').exists()).toBe(false)

    const withBadge = mount(RankList, {
      props: { rows: [...rows, { label: 'X', value: '1', frac: 0.1, badge: '1%' }] },
    })
    expect(withBadge.findAll('.rk-badge')).toHaveLength(3)
  })

  it('never uses auto/minmax for the column template (bar-alignment regression)', () => {
    const w = mount(RankList, { props: { rows } })
    const style = (w.find('.rank-list').element as HTMLElement).style.getPropertyValue('--rk-cols')
    expect(style).not.toMatch(/auto|minmax/)
  })

  it('builds the desktop and phone track templates from the optional icon and badge columns', () => {
    const plain = mount(RankList, { props: { rows } }).find('.rank-list').element as HTMLElement
    expect(plain.style.getPropertyValue('--rk-cols')).toBe('180px 1fr 62px')
    expect(plain.style.getPropertyValue('--rk-cols-sm')).toBe('minmax(0, 1fr) 62px')

    const full = mount(RankList, {
      props: { rows: [{ label: 'a', value: '1', frac: 1, icon: 'x', badge: 'b' }] },
    }).find('.rank-list').element as HTMLElement
    expect(full.style.getPropertyValue('--rk-cols')).toBe('18px 180px 60px 1fr 62px')
    expect(full.style.getPropertyValue('--rk-cols-sm')).toBe('18px minmax(0, 1fr) 60px 62px')
  })

  it('declares the bar track/fill as blocks so the bar is not invisible', async () => {
    // jsdom does not resolve scoped-SFC CSS via getComputedStyle, so this reads
    // the compiled <style> source directly rather than the rendered box.
    const raw = await import('@/components/base/RankList.vue?raw')
    const css = (raw.default as string).split('<style')[1]!
    expect(css).toMatch(/\.rk-track\s*{[^}]*display:\s*block/)
    expect(css).toMatch(/\.rk-fill\s*{[^}]*display:\s*block/)
  })

  it('floors the bar fill width at 2% so small shares stay visible', () => {
    const w = mount(RankList, { props: { rows: [{ label: 'x', value: '1', frac: 0.001 }] } })
    expect((w.find('.rk-fill').element as HTMLElement).style.width).toBe('2%')
  })

  it('without fit, never sets overflow-y hidden or the --fit class', () => {
    const w = mount(RankList, { props: { rows } })
    const el = w.find('.rank-list').element as HTMLElement
    expect(el.classList.contains('rank-list--fit')).toBe(false)
  })
})

describe('RankList fit mode', () => {
  const manyRows: RankRow[] = Array.from({ length: 20 }, (_, i) => ({
    label: `Row ${i}`,
    value: String(i),
    frac: 0.5,
  }))

  // jsdom never lays out elements (clientHeight/offsetHeight always 0).
  // Stub the prototype getter so the component's onMounted measurement works.
  function withClientHeight<T>(px: number, fn: () => T): T {
    // jsdom defines clientHeight on Element.prototype, not HTMLElement.prototype.
    const orig = Object.getOwnPropertyDescriptor(Element.prototype, 'clientHeight')
    Object.defineProperty(Element.prototype, 'clientHeight', {
      configurable: true,
      get: () => px,
    })
    try {
      return fn()
    } finally {
      if (orig) Object.defineProperty(Element.prototype, 'clientHeight', orig)
    }
  }

  // Fakes a 50px viewport over four 20px rows at 25px steps: rows end at
  // 20, 45, 70, 95, so two spill out. Spies are restored in afterEach.
  function mountOverflowing(props: Record<string, unknown> = {}) {
    const h = (k: string, v: (this: HTMLElement) => number) =>
      vi.spyOn(HTMLElement.prototype, k as 'offsetTop', 'get').mockImplementation(v as () => number)
    h('clientHeight', () => 50)
    h('scrollHeight', () => 100)
    h('offsetHeight', () => 20)
    h('offsetTop', function () {
      return Array.from(this.parentElement?.children ?? []).indexOf(this) * 25
    })
    const many = Array.from({ length: 4 }, (_, i) => ({ label: `r${i}`, value: '1', frac: 0.5 }))
    return mount(RankList, { props: { rows: many, ...props }, attachTo: document.body })
  }

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders every row and no footer with ample height', () => {
    const w = withClientHeight(2000, () =>
      mount(RankList, { props: { rows: manyRows, fit: true } }),
    )

    expect(w.findAll('.rank-row').length).toBe(manyRows.length)
    expect(w.find('.rk-footer').exists()).toBe(false)
  })

  it('captions how many rows are not fully visible when the list overflows', async () => {
    const w = mountOverflowing()
    try {
      await w.find('.rank-list').trigger('scroll')
      expect(w.find('.rk-caption').text()).toBe('2 more - scroll')
    } finally {
      w.unmount()
    }
  })

  it('names the scroller as a region only while it overflows, using the label prop', async () => {
    const w = mountOverflowing({ label: 'Origins by country' })
    try {
      await w.find('.rank-list').trigger('scroll')
      const el = w.find('.rank-list')
      expect(el.attributes('tabindex')).toBe('0')
      expect(el.attributes('role')).toBe('region')
      expect(el.attributes('aria-label')).toBe('Origins by country')
    } finally {
      w.unmount()
    }
  })

  it('falls back to the default region name when no label is given', async () => {
    const w = mountOverflowing()
    try {
      await w.find('.rank-list').trigger('scroll')
      expect(w.find('.rank-list').attributes('aria-label')).toBe('Ranked list')
    } finally {
      w.unmount()
    }
  })
})
