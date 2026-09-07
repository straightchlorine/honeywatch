import { geoNaturalEarth1, geoPath, geoGraticule10 } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'

/** One rendered country: id, alpha-2 (for the data join), name, path, centroid. */
export interface MapCountry {
  id: string
  a2: string | null
  name: string
  d: string
  centroid: [number, number]
}

export interface MapGeometry {
  width: number
  height: number
  sphere: string
  graticule: string
  countries: MapCountry[]
  /** Natural Earth I projection at the fitted scale - for city dots/arcs/sensor marker. */
  project: (lon: number, lat: number) => [number, number]
  /** Fitted projection constants, so the hi-res tier can pin to the same frame. */
  fit: { scale: number; translate: [number, number] }
  /**
   * Boundaries Natural Earth's German edition does not class as settled - lines
   * of control, indefinite and indeterminate frontiers. Drawn dotted over an
   * opaque casing so the map does not assert the Kashmir Line of Control with
   * the same confidence as the France/Germany border. One path: these carry no
   * interaction and no per-feature state.
   */
  disputedBorders: string
}

interface CountryProps {
  name?: string
}

const SPHERE = { type: 'Sphere' } as const
const WIDTH = 1600
const HEIGHT = 780
const PADDING = 8
// A handful of Natural Earth areas have no ISO code and carry their 3-letter
// ADM0_A3 id instead (sovereign base areas, Bir Tawil, disputed reefs). They
// render as plain land: nothing to join, nothing to select.
const ALPHA2 = /^[A-Z]{2}$/

/**
 * Fetch and project the world TopoJSON to SVG paths. Feature ids are ISO
 * 3166-1 alpha-2 (the key the API joins on), eliminating lookup overhead.
 * Antarctica excluded at build time. Must be held in a `shallowRef` by callers
 * (255 paths re-diffing on every render wastes performance).
 */
export async function loadMapGeometry(
  url = `${import.meta.env.BASE_URL}geo/countries.json`,
  bordersUrl = `${import.meta.env.BASE_URL}geo/borders-disputed.json`,
): Promise<MapGeometry> {
  // Parallel so the borders add no latency at the Suspense boundary.
  const [res, bres] = await Promise.all([fetch(url), fetch(bordersUrl)])
  if (!res.ok) throw new Error(`world map geometry unavailable (${res.status})`)
  if (!bres.ok) throw new Error(`disputed boundary lines unavailable (${bres.status})`)
  const topology = (await res.json()) as Topology<{
    countries: GeometryCollection<CountryProps>
  }>
  const object = topology.objects.countries
  const land = (feature(topology, object) as FeatureCollection<Geometry, CountryProps>)
    .features as Feature<Geometry, CountryProps>[]

  const projection = geoNaturalEarth1().fitExtent(
    [
      [PADDING, PADDING],
      [WIDTH - PADDING, HEIGHT - PADDING],
    ],
    { type: 'FeatureCollection', features: land },
  )
  const path = geoPath(projection)

  const btop = (await bres.json()) as Topology<{ borders: GeometryCollection }>
  const disputedBorders = (
    feature(btop, btop.objects.borders) as FeatureCollection<Geometry>
  ).features
    .map((f) => path(f))
    .filter(Boolean)
    .join('')

  const countries: MapCountry[] = []
  for (const f of land) {
    const d = path(f)
    if (!d) continue
    const id = String(f.id)
    countries.push({
      id,
      a2: ALPHA2.test(id) ? id : null,
      name: f.properties?.name ?? id,
      d,
      centroid: path.centroid(f),
    })
  }

  const k = projection.scale()
  const [tx, ty] = projection.translate()
  // Inline Natural Earth I formula to skip geoPath overhead for per-point
  // projection (city markers, arcs, sensor marker).
  function project(lon: number, lat: number): [number, number] {
    const l = (lon * Math.PI) / 180
    const p = (lat * Math.PI) / 180
    const p2 = p * p
    const p4 = p2 * p2
    const x =
      l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    const y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return [tx + k * x, ty - k * y]
  }

  return {
    width: WIDTH,
    height: HEIGHT,
    sphere: path(SPHERE) ?? '',
    graticule: path(geoGraticule10()) ?? '',
    countries,
    project,
    fit: { scale: k, translate: [tx, ty] },
    disputedBorders,
  }
}
