import { geoEqualEarth, geoGraticule10, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { feature, mesh } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'

/** One rendered country: numeric ISO id, display name, projected SVG path. */
export interface CountryPath {
  id: string
  name: string
  d: string
}

/** Everything the SVG needs, pre-projected once. Geometry is static; only
 *  fills change as attack counts poll in, so this is computed a single time. */
export interface WorldGeometry {
  width: number
  height: number
  sphere: string
  graticule: string
  borders: string
  coast: string
  countries: CountryPath[]
}

interface CountryProps {
  name?: string
}

const SPHERE = { type: 'Sphere' } as const
const WIDTH = 975

/**
 * Fetch the world-atlas TopoJSON and project it with Equal Earth.
 *
 * Served from `public/geo/` (HTTP-cached asset, never bundled as JS). d3-geo
 * does pure calculation here -- it never touches the DOM; Vue renders the
 * resulting path strings. Feature ids are the zero-padded numeric ISO strings
 * (e.g. "004") used as the choropleth join key.
 */
export async function loadWorldGeometry(
  url = `${import.meta.env.BASE_URL}geo/countries-110m.json`,
): Promise<WorldGeometry> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`world map geometry unavailable (${res.status})`)
  const topology = (await res.json()) as Topology<{ countries: GeometryCollection<CountryProps> }>
  const object = topology.objects.countries
  const collection = feature(topology, object) as FeatureCollection<Geometry, CountryProps>

  const projection = geoEqualEarth().fitWidth(WIDTH, SPHERE)
  const path = geoPath(projection)
  const height = Math.ceil(path.bounds(SPHERE)[1][1])

  const countries: CountryPath[] = []
  for (const f of collection.features as Feature<Geometry, CountryProps>[]) {
    const d = path(f)
    if (!d) continue
    countries.push({ id: String(f.id), name: f.properties?.name ?? String(f.id), d })
  }

  return {
    width: WIDTH,
    height,
    sphere: path(SPHERE) ?? '',
    graticule: path(geoGraticule10()) ?? '',
    borders: path(mesh(topology, object, (a, b) => a !== b)) ?? '',
    coast: path(mesh(topology, object, (a, b) => a === b)) ?? '',
    countries,
  }
}
