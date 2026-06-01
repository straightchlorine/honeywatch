/**
 * Amber choropleth scale for the world map. The shared sqrt ramp + floor live in
 * `components/charts/useHeatScale` (also used by the activity heatmap); this
 * module owns the map-specific numeric-id Map lookup and the no-data land color
 * so country fills never read as "zero".
 */
import { HEAT_FLOOR, rampColor } from '@/components/charts/useHeatScale'

export interface Choropleth {
  /** Fill for a country by numeric ISO id; no/zero data -> the land color. */
  fill: (numericId: string) => string
  /** Highest observed count (0 if no data). */
  max: number
  /** Low -> high colors for the legend gradient. */
  rampStops: string[]
}

const LAND = 'var(--map-land)'

export function useChoropleth(counts: Map<string, number>): Choropleth {
  let max = 0
  for (const value of counts.values()) if (value > max) max = value
  const denom = max > 0 ? Math.sqrt(max) : 1

  function fill(numericId: string): string {
    const count = counts.get(numericId) ?? 0
    if (count <= 0) return LAND
    const t = HEAT_FLOOR + (1 - HEAT_FLOOR) * (Math.sqrt(count) / denom)
    return rampColor(t)
  }

  const rampStops =
    max > 0 ? Array.from({ length: 9 }, (_, i) => rampColor(HEAT_FLOOR + (1 - HEAT_FLOOR) * (i / 8))) : []

  return { fill, max, rampStops }
}
