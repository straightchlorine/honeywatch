import type { HeatmapPointResponse } from '@/api/generated/types.gen'

/** Weekday labels indexed by Postgres date_part('dow'): 0=Sunday .. 6=Saturday. */
export const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const

export interface HeatmapGrid {
  /** grid[weekday 0=Sun..6=Sat][hour 0..23] = session count (0 when no data). */
  grid: number[][]
  /** Highest single-cell count (0 when empty). */
  max: number
}

/**
 * Densify sparse `/stats/heatmap` response into full 7x24 grid.
 *
 * Arguments:
 *   points: HeatmapPointResponse[] — sparse heatmap data from API
 *
 * Returns:
 *   HeatmapGrid — 7x24 grid (weekday 0=Sun..6=Sat; hour 0..23) + max
 *
 * Missing cells default to 0; out-of-range points ignored.
 * Weekday convention matches Postgres date_part('dow').
 */
export function buildHeatmapGrid(points: HeatmapPointResponse[]): HeatmapGrid {
  const grid: number[][] = Array.from({ length: 7 }, () => new Array<number>(24).fill(0))
  let max = 0
  for (const p of points) {
    if (p.weekday < 0 || p.weekday > 6 || p.hour < 0 || p.hour > 23) continue
    grid[p.weekday]![p.hour] = p.count
    if (p.count > max) max = p.count
  }
  return { grid, max }
}
