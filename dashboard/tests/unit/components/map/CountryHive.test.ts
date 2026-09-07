import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

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

function mountHive(countries: CountryRowResponse[]) {
  return mount(CountryHive, {
    props: { countries },
    global: { stubs: { RouterLink: true } },
  })
}

describe('CountryHive contrast', () => {
  it('renders the max-count cell code with dark ink, a low-count cell without', () => {
    const countries = [
      row({ country_code: 'NL', country: 'Netherlands', sessions: 37000 }),
      row({ country_code: 'AA', country: 'Somewhere', sessions: 5 }),
    ]
    const w = mountHive(countries)
    const codeTexts = w.findAll('.hex-code')
    expect(codeTexts).toHaveLength(2)
    expect(codeTexts[0]!.classes()).toContain('dark')
    expect(codeTexts[1]!.classes()).not.toContain('dark')

    const countTexts = w.findAll('.hex-count')
    expect(countTexts[0]!.classes()).toContain('dark')
    expect(countTexts[1]!.classes()).not.toContain('dark')
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
