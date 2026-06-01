/**
 * Amber choropleth scale for the world map. The shared sqrt ramp + floor live in
 * `components/charts/useHeatScale` (also used by the activity heatmap); this
 * module owns the map-specific numeric-id Map lookup and the no-data land color
 * so country fills never read as "zero".
 */
import { useHeatScale } from '@/components/charts/useHeatScale'

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
  // The sqrt ramp + floor + legend stops are owned by useHeatScale; this module
  // only adds the map-specific numeric-id lookup and the `--map-land` zero color.
  const scale = useHeatScale(counts.values(), { zeroColor: LAND })
  return {
    fill: (numericId) => scale.fill(counts.get(numericId) ?? 0),
    max: scale.max,
    rampStops: scale.rampStops,
  }
}
