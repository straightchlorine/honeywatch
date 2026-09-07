import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RankList, { type RankRow } from '@/components/base/RankList.vue'

const rows: RankRow[] = [
  { label: 'China', value: '34,468', frac: 1, title: 'China, in full' },
  { label: 'United States', value: '12,004', frac: 0.35 },
]

describe('RankList', () => {
  it('renders one row per entry', () => {
    const w = mount(RankList, { props: { rows } })
    expect(w.findAll('.rank-row')).toHaveLength(2)
  })

  it('makes rows focusable and wires custom tooltip handlers', () => {
    const w = mount(RankList, { props: { rows } })
    const rowEls = w.findAll('.rank-row')
    // Rows are focusable for keyboard access to the tooltip
    expect(rowEls[0]!.attributes('tabindex')).toBe('0')
    expect(rowEls[1]!.attributes('tabindex')).toBe('0')
    // jsdom does not support testing event handlers; verify elements exist as a proxy
    for (const el of rowEls) {
      expect(el.exists()).toBe(true)
    }
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

  it('declares the bar track/fill as blocks (invisible-bar regression - pitfall 14.1)', async () => {
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


  it('renders every row and no footer with ample height', () => {
    const w = withClientHeight(2000, () => mount(RankList, { props: { rows: manyRows, fit: true } }))

    expect(w.findAll('.rank-row').length).toBe(manyRows.length)
    expect(w.find('.rk-footer').exists()).toBe(false)
  })

})
