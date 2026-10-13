import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import CountryHive from '@/components/map/CountryHive.vue'
import type { CountryRowResponse } from '@/api/generated/types.gen'

function row(overrides: Partial<CountryRowResponse>): CountryRowResponse {
  return {
    country_code: 'XX',
    country: 'Nowhere',
    sessions: 1,
    distinct_ips: 1,
    attempts: 1,
    success_rate: 0,
    ...overrides,
  } as CountryRowResponse
}

function mountHive(countries: CountryRowResponse[], router = makeRouter()) {
  return mount(CountryHive, {
    props: { countries },
    global: { plugins: [router], stubs: { RouterLink: true } },
  })
}

function makeRouter() {
  return createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: {} }] })
}

// Keyboard tests need real focus, so they mount on document.body. Tracked here
// so afterEach unmounts them even when an assertion throws.
const attached: { unmount: () => void }[] = []
afterEach(() => {
  while (attached.length) attached.pop()!.unmount()
})

function mountAttached(countries: CountryRowResponse[], router = makeRouter()) {
  const w = mount(CountryHive, {
    attachTo: document.body,
    props: { countries },
    global: { plugins: [router], stubs: { RouterLink: true } },
  })
  attached.push(w)
  return w
}

function countries24(): CountryRowResponse[] {
  return Array.from({ length: 24 }, (_, i) =>
    row({ country_code: `C${i}`, country: `C${i}`, sessions: 100 - i }),
  )
}

const hexCells = () => [...document.querySelectorAll<SVGElement>('.hex-cell')]

// The roving stop is the only element with tabindex="0".
function expectSingleStop(selector: string, el: Element | undefined): void {
  const stops = [...document.querySelectorAll(selector)].filter(
    (n) => n.getAttribute('tabindex') === '0',
  )
  expect(stops).toHaveLength(1)
  expect(stops[0]).toBe(el)
}

async function press(key: string): Promise<void> {
  document.activeElement!.dispatchEvent(
    new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
  )
  await flushPromises()
}

describe('CountryHive contrast', () => {
  it('inks the max-count cell dark and a low-count cell light', () => {
    const countries = [
      row({ country_code: 'NL', country: 'Netherlands', sessions: 37000 }),
      row({ country_code: 'AA', country: 'Somewhere', sessions: 5 }),
    ]
    const w = mountHive(countries)
    const codeTexts = w.findAll('.hex-code')
    expect(codeTexts).toHaveLength(2)
    expect(codeTexts[0]!.attributes('style')).toContain('rgb(18, 13, 9)')
    expect(codeTexts[1]!.attributes('style')).not.toContain('rgb(18, 13, 9)')

    const countTexts = w.findAll('.hex-count')
    expect(countTexts[0]!.attributes('style')).toContain('rgb(18, 13, 9)')
    expect(countTexts[1]!.attributes('style')).not.toContain('rgb(18, 13, 9)')
  })
})

describe('CountryHive hex-of-hexes packing', () => {
  function makeCountries(n: number): CountryRowResponse[] {
    return Array.from({ length: n }, (_, i) =>
      row({ country_code: `C${i}`, country: `Country ${i}`, sessions: n - i + 1 }),
    )
  }

  it('packs 24 countries into 5 rows of 4/5/6/5/4 cells', () => {
    const w = mountHive(makeCountries(24))
    const cells = w.findAll('.hex-cell')
    expect(cells).toHaveLength(24)

    // Group rendered cells by row via the flag <text>'s y attribute (a direct
    // function of cell.cy), rather than the polygon points which are only
    // relative offsets from the centre.
    const groups = w.findAll('.hive-hex')
    const cyValues = groups.map((g) => Number(g.find('text').attributes('y')))
    const uniqueRows = [...new Set(cyValues)].sort((a, b) => a - b)
    expect(uniqueRows).toHaveLength(5)

    const counts = uniqueRows.map((cy) => cyValues.filter((v) => v === cy).length)
    expect(counts).toEqual([4, 5, 6, 5, 4])
  })

  it('centres the first and last row on the same axis as the widest row', () => {
    const w = mountHive(makeCountries(24))
    const groups = w.findAll('.hive-hex')

    // The first <text> (flag) in each cell carries x = cell.cx.
    const rowsByY = new Map<number, number[]>()
    groups.forEach((g) => {
      const texts = g.findAll('text')
      const y = Number(texts[0]!.attributes('y'))
      const x = Number(texts[0]!.attributes('x'))
      const list = rowsByY.get(y) ?? []
      list.push(x)
      rowsByY.set(y, list)
    })

    const ys = [...rowsByY.keys()].sort((a, b) => a - b)
    const midOf = (y: number) => {
      const xs = rowsByY.get(y)!
      return (Math.min(...xs) + Math.max(...xs)) / 2
    }

    const widestY = ys.reduce((best, y) =>
      rowsByY.get(y)!.length > rowsByY.get(best)!.length ? y : best,
    )
    const widestMid = midOf(widestY)

    expect(Math.abs(midOf(ys[0]!) - widestMid)).toBeLessThan(1)
    expect(Math.abs(midOf(ys[ys.length - 1]!) - widestMid)).toBeLessThan(1)
  })

  it('renders a short list without padding and shrinks the viewBox', () => {
    const w24 = mountHive(makeCountries(24))
    const w7 = mountHive(makeCountries(7))

    expect(w7.findAll('.hex-cell')).toHaveLength(7)

    const viewBox24 = w24.find('svg').attributes('viewBox')!
    const viewBox7 = w7.find('svg').attributes('viewBox')!
    const h24 = Number(viewBox24.split(' ')[3])
    const h7 = Number(viewBox7.split(' ')[3])
    expect(h7).toBeLessThan(h24)
  })
})

describe('CountryHive view toggle', () => {
  it('persists Table in ?view=table and drops the param for Hive', async () => {
    const router = makeRouter()
    await router.push('/')
    const w = mountHive([row({})], router)
    const chips = w.findAll('button')
    await chips.find((b) => b.text() === 'Table')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.view).toBe('table')
    expect(w.find('.rank-table').exists()).toBe(true)
    expect(w.find('.hive-svg').exists()).toBe(false)

    await w
      .findAll('button')
      .find((b) => b.text() === 'Hive')!
      .trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.view).toBeUndefined()
    expect(w.find('.hive-svg').exists()).toBe(true)
    expect(w.find('.rank-table').exists()).toBe(false)
  })

  it('renders the table on load when the URL carries ?view=table', async () => {
    const router = makeRouter()
    await router.push({ path: '/', query: { view: 'table' } })
    const w = mountHive([row({ country_code: 'NL', country: 'Netherlands' })], router)
    await flushPromises()
    expect(w.find('.rank-table').exists()).toBe(true)
    expect(w.find('.hive-svg').exists()).toBe(false)
  })
})

describe('CountryHive roving tabindex (hive)', () => {
  it('is one Tab stop; Left/Right walk the order and clamp at both ends', async () => {
    mountAttached(countries24())
    await flushPromises()
    const cells = hexCells()
    expect(cells).toHaveLength(24)
    expectSingleStop('.hex-cell', cells[0])

    cells[0]!.focus()
    await press('ArrowLeft') // clamp at the first cell
    expect(document.activeElement).toBe(cells[0])

    await press('ArrowRight')
    expect(document.activeElement).toBe(cells[1])
    expectSingleStop('.hex-cell', cells[1])

    await press('ArrowLeft')
    expect(document.activeElement).toBe(cells[0])
    expectSingleStop('.hex-cell', cells[0])
  })

  it('ArrowDown and ArrowUp take the nearest cell in the adjacent row', async () => {
    mountAttached(countries24())
    await flushPromises()
    const cells = hexCells()

    // Row 0 has 4 cells, row 1 has 5 and is offset half a hex. From cell 1 the
    // row-1 cells 5 and 6 are at exactly the same x distance (the distances are
    // bit-identical). onKeydown only replaces its pick on a clearly smaller dx,
    // so the first match in DOM order wins: the leftmost, cell 5.
    cells[1]!.focus()
    await press('ArrowDown')
    expect(document.activeElement).toBe(cells[5])
    expectSingleStop('.hex-cell', cells[5])

    // Going back up from cell 5, row-0 cells 0 and 1 are equidistant up to float
    // noise (~6e-14); the tie resolves to the leftmost, cell 0, not to the noise.
    cells[5]!.focus()
    await press('ArrowUp')
    expect(document.activeElement).toBe(cells[0])

    // Cell 8 is the right end of row 1 and has exactly one row-0 neighbour (3).
    cells[8]!.focus()
    await press('ArrowUp')
    expect(document.activeElement).toBe(cells[3])

    // Row 0 has no row above, so the focus stays put.
    await press('ArrowUp')
    expect(document.activeElement).toBe(cells[3])

    // Row 4 (cells 20-23) is the last row, so ArrowDown stays put.
    cells[23]!.focus()
    await press('ArrowDown')
    expect(document.activeElement).toBe(cells[23])
  })

  it('Home and End hit the ends; Enter and Space select the focused country', async () => {
    const w = mountAttached(countries24())
    await flushPromises()
    const cells = hexCells()

    cells[0]!.focus()
    await press('End')
    expect(document.activeElement).toBe(cells[23])
    expectSingleStop('.hex-cell', cells[23])

    await press('Home')
    expect(document.activeElement).toBe(cells[0])
    expectSingleStop('.hex-cell', cells[0])

    cells[7]!.focus()
    await press('Enter')
    expect(w.emitted('update:selected')).toContainEqual(['C7'])

    cells[3]!.focus()
    await press(' ')
    expect(w.emitted('update:selected')).toContainEqual(['C3'])
  })
})

describe('CountryHive roving tabindex (table)', () => {
  it('is one Tab stop; ArrowDown/ArrowUp/Home/End move focus and the stop', async () => {
    const router = makeRouter()
    await router.push({ path: '/', query: { view: 'table' } })
    mountAttached(countries24(), router)
    await flushPromises()

    const rowSel = '.rank-table tbody tr'
    const rows = () => [...document.querySelectorAll<HTMLElement>(rowSel)]
    expect(rows()).toHaveLength(24)
    expectSingleStop(rowSel, rows()[0])

    rows()[0]!.focus()
    await press('ArrowDown')
    expect(document.activeElement).toBe(rows()[1])
    expectSingleStop(rowSel, rows()[1])

    await press('ArrowUp')
    expect(document.activeElement).toBe(rows()[0])
    expectSingleStop(rowSel, rows()[0])

    await press('ArrowUp') // clamp at the first row
    expect(document.activeElement).toBe(rows()[0])

    await press('End')
    expect(document.activeElement).toBe(rows()[23])
    expectSingleStop(rowSel, rows()[23])

    await press('ArrowDown') // clamp at the last row
    expect(document.activeElement).toBe(rows()[23])

    await press('Home')
    expect(document.activeElement).toBe(rows()[0])
    expectSingleStop(rowSel, rows()[0])
  })
})
