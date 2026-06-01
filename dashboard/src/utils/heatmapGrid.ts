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
 * Densify the sparse `/stats/heatmap` response into a full 7x24 matrix.
 *
 * `weekday` follows Postgres `date_part('dow', ...)` = 0=Sunday .. 6=Saturday
 * (see api/src/services/stats.py). NOTE: the generated type's "0=Monday" doc
 * comment is stale/wrong -- trust 0=Sunday. Missing (weekday, hour) cells
 * default to 0; out-of-range points are ignored rather than throwing.
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
