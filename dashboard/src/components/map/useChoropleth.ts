/**
 * Amber choropleth scale, driven entirely by CSS tokens (theme-reactive, zero
 * runtime color deps). Attack counts are heavily skewed -- a sqrt scale keeps
 * "this country is an order of magnitude hotter" legible where a linear scale
 * would collapse the long tail into one shade. A floor lifts the lowest data
 * color clearly above the no-data land color so land never reads as "zero".
 */
export interface Choropleth {
  /** Fill for a country by numeric ISO id; no/zero data -> the land color. */
  fill: (numericId: string) => string
  /** Highest observed count (0 if no data). */
  max: number
  /** Low -> high colors for the legend gradient. */
  rampStops: string[]
}

const LAND = 'var(--map-land)'
const FLOOR = 0.15

/** Map a normalized intensity (0..1) onto the amber ramp via token color-mix:
 *  --accent-dim -> --accent -> --warning (gold). */
function rampColor(t: number): string {
  const clamped = t < 0 ? 0 : t > 1 ? 1 : t
  if (clamped <= 0.5) {
    const pct = Math.round((clamped / 0.5) * 100)
    return `color-mix(in srgb, var(--accent) ${pct}%, var(--accent-dim))`
  }
  const pct = Math.round(((clamped - 0.5) / 0.5) * 100)
  return `color-mix(in srgb, var(--warning) ${pct}%, var(--accent))`
}

export function useChoropleth(counts: Map<string, number>): Choropleth {
  let max = 0
  for (const value of counts.values()) if (value > max) max = value
  const denom = max > 0 ? Math.sqrt(max) : 1

  function fill(numericId: string): string {
    const count = counts.get(numericId) ?? 0
    if (count <= 0) return LAND
    const t = FLOOR + (1 - FLOOR) * (Math.sqrt(count) / denom)
    return rampColor(t)
  }

  const rampStops =
    max > 0 ? Array.from({ length: 9 }, (_, i) => rampColor(FLOOR + (1 - FLOOR) * (i / 8))) : []

  return { fill, max, rampStops }
}
