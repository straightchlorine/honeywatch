import { describe, expect, it } from 'vitest'

import { buildHeatmapGrid, WEEKDAY_LABELS } from '@/utils/heatmapGrid'

describe('buildHeatmapGrid', () => {
  it('builds a full 7x24 grid with zeros for missing cells', () => {
    const { grid, max } = buildHeatmapGrid([{ weekday: 2, hour: 14, count: 5 }])
    expect(grid).toHaveLength(7)
    for (const row of grid) expect(row).toHaveLength(24)
    expect(grid[2]![14]).toBe(5)
    expect(grid[0]![0]).toBe(0)
    expect(max).toBe(5)
  })

  it('treats weekday 0 as Sunday (guards the stale "0=Monday" type comment)', () => {
    expect(WEEKDAY_LABELS[0]).toBe('Sun')
    const { grid } = buildHeatmapGrid([{ weekday: 0, hour: 9, count: 3 }])
    expect(grid[0]![9]).toBe(3)
  })

  it('ignores out-of-range weekday/hour points', () => {
    const { grid, max } = buildHeatmapGrid([
      { weekday: 7, hour: 0, count: 9 },
      { weekday: 0, hour: 24, count: 9 },
      { weekday: -1, hour: 1, count: 9 },
    ])
    expect(max).toBe(0)
    expect(grid.flat().every((n) => n === 0)).toBe(true)
  })

  it('returns max 0 and an all-zero grid for empty input', () => {
    const { grid, max } = buildHeatmapGrid([])
    expect(max).toBe(0)
    expect(grid.flat()).toHaveLength(168)
    expect(grid.flat().every((n) => n === 0)).toBe(true)
  })
})
