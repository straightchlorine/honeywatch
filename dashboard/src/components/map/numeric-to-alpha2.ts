// Reverse of ALPHA2_TO_NUMERIC: numeric TopoJSON feature id (zero-padded
// string, e.g. '840') -> ISO 3166-1 alpha-2 ('US'). Inverted once at module
// load. Used to turn a clicked/activated map country back into the alpha-2 code
// the Countries page filters on.
import { ALPHA2_TO_NUMERIC } from './alpha2-to-numeric'

export const NUMERIC_TO_ALPHA2: Readonly<Record<string, string>> = Object.freeze(
  Object.fromEntries(Object.entries(ALPHA2_TO_NUMERIC).map(([a2, num]) => [num, a2])),
)
