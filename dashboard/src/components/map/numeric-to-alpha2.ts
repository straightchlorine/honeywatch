// Numeric TopoJSON id → alpha-2; frozen at module load.
import { ALPHA2_TO_NUMERIC } from './alpha2-to-numeric'

export const NUMERIC_TO_ALPHA2: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(Object.entries(ALPHA2_TO_NUMERIC).map(([a2, num]) => [num, a2])),
)
