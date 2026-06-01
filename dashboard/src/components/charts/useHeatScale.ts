/**
 * Amber heat scale shared by the world-map choropleth and the activity heatmap.
 *
 * Attack counts are heavily skewed, so a sqrt scale keeps an "order of magnitude
 * hotter" cell legible where a linear scale collapses the long tail into one
 * shade. A floor lifts the lowest data color clearly above the zero color so a
 * single session never reads as "no data". Driven entirely by CSS tokens
 * (theme-reactive, zero runtime color deps).
 *
 * `useChoropleth` (map) reuses `rampColor` + `HEAT_FLOOR` but keeps its own
 * numeric-id Map lookup and `--map-land` zero color; the heatmap uses
 * `useHeatScale` directly with a `--bg-2` zero color.
 */

export const HEAT_FLOOR = 0.15

/** Map a normalized intensity (0..1) onto the amber ramp via token color-mix:
 *  --accent-dim -> --accent -> --warning (gold). */
export function rampColor(t: number): string {
  const clamped = t < 0 ? 0 : t > 1 ? 1 : t
  if (clamped <= 0.5) {
    const pct = Math.round((clamped / 0.5) * 100)
    return `color-mix(in srgb, var(--accent) ${pct}%, var(--accent-dim))`
  }
  const pct = Math.round(((clamped - 0.5) / 0.5) * 100)
  return `color-mix(in srgb, var(--warning) ${pct}%, var(--accent))`
}

export interface HeatScale {
  /** Fill for a single count; `<= 0` returns the zero color. */
  fill: (count: number) => string
  /** Highest observed count (0 if no data). */
  max: number
  /** Low -> high colors for the legend gradient ([] when no data). */
  rampStops: string[]
}

export function useHeatScale(
  counts: Iterable<number>,
  opts: { zeroColor?: string } = {},
): HeatScale {
  const zeroColor = opts.zeroColor ?? 'var(--bg-2)'
  let max = 0
  for (const v of counts) if (v > max) max = v
  const denom = max > 0 ? Math.sqrt(max) : 1

  function fill(count: number): string {
    if (count <= 0) return zeroColor
    const t = HEAT_FLOOR + (1 - HEAT_FLOOR) * (Math.sqrt(count) / denom)
    return rampColor(t)
  }

  const rampStops =
    max > 0
      ? Array.from({ length: 9 }, (_, i) => rampColor(HEAT_FLOOR + (1 - HEAT_FLOOR) * (i / 8)))
      : []

  return { fill, max, rampStops }
}
