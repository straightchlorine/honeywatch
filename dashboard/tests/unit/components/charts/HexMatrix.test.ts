import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import HexMatrix from '@/components/charts/HexMatrix.vue'

describe('HexMatrix', () => {
  it('renders one hex cell per user x password combination', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [{ label: '123456', count: 10 }, { label: 'root', count: 5 }],
        pairs: [
          { username: 'admin', password: '123456', count: 10, accepted: false },
          { username: 'admin', password: 'root', count: 5, accepted: false },
        ],
      },
    })
    expect(w.findAll('polygon.mcell')).toHaveLength(2)
  })

  it('rings an accepted pair', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [{ label: '123456', count: 10 }],
        pairs: [{ username: 'admin', password: '123456', count: 10, accepted: true }],
      },
    })
    expect(w.find('polygon.mcell').attributes('stroke')).toBe('var(--ok)')
  })

  it('flips a mid-bright cell (heat between 0.37 and 0.62) to dark ink', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [
          { label: 'a', count: 100 },
          { label: 'b', count: 20 },
        ],
        passwords: [{ label: 'p', count: 1 }],
        pairs: [
          { username: 'a', password: 'p', count: 100, accepted: false },
          { username: 'b', password: 'p', count: 20, accepted: false },
        ],
      },
    })
    const labels = w.findAll('.mx-cell-label')
    expect(labels).toHaveLength(2)
    expect(labels[0]!.classes()).toContain('dark')
    expect(labels[1]!.classes()).toContain('dark')
  })

  it('renders an unobserved cell with no number and no outcome claim', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [
          { label: '123456', count: 10 },
          { label: 'hunter2', count: 3 },
        ],
        pairs: [
          { username: 'admin', password: '123456', count: 10, accepted: false },
          { username: 'ghost', password: 'hunter2', count: 2, accepted: false },
        ],
      },
    })
    const cells = w.findAll('polygon.mcell')
    expect(cells).toHaveLength(2)
    const unobserved = cells[1]! // admin x hunter2
    expect(w.findAll('.mx-cell-label')).toHaveLength(1) // only admin/123456 was observed
    expect(unobserved.attributes('fill')).toBe('var(--surface-2)')
    expect(unobserved.attributes('stroke')).toBe('none')
    const aria = unobserved.attributes('aria-label')!
    expect(aria).toContain('never tried')
    expect(aria).not.toMatch(/rejected|accepted|attempts/i)
  })

  it('emits select with the cell payload on click, for both observed and unobserved cells', async () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [
          { label: '123456', count: 10 },
          { label: 'hunter2', count: 3 },
        ],
        pairs: [
          { username: 'admin', password: '123456', count: 10, accepted: true },
          { username: 'ghost', password: 'hunter2', count: 1, accepted: false },
        ],
      },
    })
    const cells = w.findAll('polygon.mcell')

    await cells[0]!.trigger('click')
    expect(w.emitted('select')![0]).toEqual([
      { username: 'admin', password: '123456', count: 10, accepted: true, observed: true },
    ])

    await cells[1]!.trigger('click')
    expect(w.emitted('select')![1]).toEqual([
      { username: 'admin', password: 'hunter2', count: 0, accepted: false, observed: false },
    ])
  })

  it('emits select on Enter and Space but not other keys', async () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [{ label: '123456', count: 10 }],
        pairs: [{ username: 'admin', password: '123456', count: 10, accepted: false }],
      },
    })
    const cell = w.find('polygon.mcell')

    await cell.trigger('keydown', { key: 'a' })
    expect(w.emitted('select')).toBeUndefined()

    await cell.trigger('keydown', { key: 'Enter' })
    await cell.trigger('keydown', { key: ' ' })
    expect(w.emitted('select')).toHaveLength(2)
  })

  it('draws a selection ring only for the cell matching selectedKey', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [
          { label: '123456', count: 10 },
          { label: 'root', count: 5 },
        ],
        pairs: [
          { username: 'admin', password: '123456', count: 10, accepted: false },
          { username: 'admin', password: 'root', count: 5, accepted: false },
        ],
        selectedKey: 'admin|root',
      },
    })
    expect(w.findAll('.mx-select-ring')).toHaveLength(1)
  })

  it('emits shown with the drawn column count (jsdom ResizeObserver stub returns candidatePasswords.length)', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [
          { label: '123456', count: 10 },
          { label: 'root', count: 5 },
        ],
        pairs: [
          { username: 'admin', password: '123456', count: 5, accepted: false },
          { username: 'admin', password: 'root', count: 2, accepted: false },
        ],
      },
    })
    expect(w.emitted('shown')).toEqual([[2]])
  })

  it('drops a username with no observed pair entirely - no all-empty row', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [
          { label: 'admin', count: 10 },
          { label: 'deploy', count: 0 },
        ],
        passwords: [{ label: '123456', count: 10 }],
        pairs: [{ username: 'admin', password: '123456', count: 10, accepted: false }],
      },
    })
    expect(w.findAll('polygon.mcell')).toHaveLength(1)
    expect(w.text()).not.toContain('deploy')
  })

  it('drops a password with no observed pair entirely - no all-empty column', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [
          { label: '123456', count: 10 },
          { label: 'neverused', count: 0 },
        ],
        pairs: [{ username: 'admin', password: '123456', count: 10, accepted: false }],
      },
    })
    expect(w.findAll('polygon.mcell')).toHaveLength(1)
    expect(w.text()).not.toContain('neverused')
  })

  it('renders nothing and does not crash when there are no observed pairs at all', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [{ label: '123456', count: 10 }],
        pairs: [],
      },
    })
    expect(w.findAll('polygon.mcell')).toHaveLength(0)
    expect(w.findAll('.mx-axis')).toHaveLength(0)
    expect(w.emitted('shown')).toEqual([[0]])
    // Prevent NaN/Infinity from division by zero in empty grid.
    const viewBox = w.find('svg').attributes('viewBox')!
    expect(viewBox).not.toMatch(/NaN|Infinity/)
  })

  it('grows the viewBox height for a longer password label, but stops growing past the 8-char cap', () => {
    const heightFor = (password: string): number => {
      const w = mount(HexMatrix, {
        props: {
          users: [{ label: 'admin', count: 10 }],
          passwords: [{ label: password, count: 10 }],
          pairs: [{ username: 'admin', password, count: 10, accepted: false }],
        },
      })
      return Number(w.find('svg').attributes('viewBox')!.split(' ')[3])
    }
    const short = heightFor('123456')
    const long = heightFor('1q2w3r4e5t')
    const longer = heightFor('1q2w3r4e5t6y7u8i9o0p')
    expect(long).toBeGreaterThan(short)
    expect(longer).toBe(long)
  })

  it("keeps column 0's rotated label reach inside the viewBox's left edge", () => {
    // Rotated text-anchor="end" at column 0 swings left; risk of clipping x=0.
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'pi', count: 10 }],
        passwords: [{ label: 'letmein123456', count: 10 }],
        pairs: [{ username: 'pi', password: 'letmein123456', count: 10, accepted: false }],
      },
    })
    const label = w.find('text.mx-axis[transform]')
    const x = Number(label.attributes('x'))
    // Replicates colLabelReach() formula from HexMatrix.vue with MAX_LABEL_CHARS cap.
    const charW = 7
    const ascent = 12
    const safety = 4 // AXIS_SAFETY in HexMatrix.vue
    const rad = (38 * Math.PI) / 180
    const cappedW = 8 * charW
    const leftReach = cappedW * Math.cos(rad) + ascent * Math.sin(rad) + safety
    expect(x - leftReach).toBeGreaterThanOrEqual(0)
  })

  it('reverses row order so the most-attempted username renders at the BOTTOM, while column order (most-attempted password first) is unchanged', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [
          { label: 'root', count: 900 }, // most-attempted
          { label: 'admin', count: 100 },
        ],
        passwords: [
          { label: '123456', count: 500 }, // most-attempted
          { label: 'toor', count: 100 },
        ],
        pairs: [
          { username: 'root', password: '123456', count: 400, accepted: false },
          { username: 'root', password: 'toor', count: 100, accepted: false },
          { username: 'admin', password: '123456', count: 100, accepted: false },
          { username: 'admin', password: 'toor', count: 50, accepted: false },
        ],
      },
    })
    const rowLabels = w.findAll('text.mx-axis').filter((t) => !t.attributes('transform'))
    expect(rowLabels.map((t) => t.text())).toEqual(['admin', 'root'])
    const ys = rowLabels.map((t) => Number(t.attributes('y')))
    expect(ys[1]).toBeGreaterThan(ys[0]!)

    const colLabels = w.findAll('text.mx-axis').filter((t) => t.attributes('transform'))
    expect(colLabels.map((t) => t.text())).toEqual(['123456', 'toor'])
    const xs = colLabels.map((t) => Number(t.attributes('x')))
    expect(xs[0]).toBeLessThan(xs[1]!)
  })

  it('truncates a label over 8 characters with a marker, on both axes, while keeping the full value in aria-label, the cell aria-label, and the select payload', async () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'administrator', count: 10 }], // 13 chars
        passwords: [{ label: 'letmein123', count: 10 }], // 10 chars
        pairs: [{ username: 'administrator', password: 'letmein123', count: 10, accepted: true }],
      },
    })
    const marker = '\u2026'
    const rowLabel = w.find('text.mx-axis:not([transform])')
    const colLabel = w.find('text.mx-axis[transform]')

    expect(rowLabel.text()).toBe(`adminis${marker}`)
    expect(colLabel.text()).toBe(`letmein${marker}`)
    expect(rowLabel.text()).toHaveLength(8)
    expect(colLabel.text()).toHaveLength(8)

    expect(rowLabel.attributes('aria-label')).toBe('administrator')
    expect(colLabel.attributes('aria-label')).toBe('letmein123')

    const cell = w.find('polygon.mcell')
    expect(cell.attributes('aria-label')).toContain('administrator')
    expect(cell.attributes('aria-label')).toContain('letmein123')

    await cell.trigger('click')
    expect(w.emitted('select')![0]).toEqual([
      {
        username: 'administrator',
        password: 'letmein123',
        count: 10,
        accepted: true,
        observed: true,
      },
    ])
  })

  it('does not truncate a label that is exactly 8 characters (the marker only appears once a label EXCEEDS the cap)', () => {
    const w = mount(HexMatrix, {
      props: {
        users: [{ label: 'admin', count: 10 }],
        passwords: [{ label: 'password', count: 10 }], // exactly 8 chars
        pairs: [{ username: 'admin', password: 'password', count: 10, accepted: false }],
      },
    })
    const colLabel = w.find('text.mx-axis[transform]')
    expect(colLabel.text()).toBe('password')
    expect(colLabel.attributes('aria-label')).toBe('password')
  })
})
