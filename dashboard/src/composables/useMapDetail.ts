import { computed, shallowRef, watch, type Ref, type ShallowRef } from 'vue'
import { geoNaturalEarth1, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'

/**
 * Swap the drawn country/border geometry for a coarser or finer tier than the
 * always-loaded base (countries.json, dp 20%). A tier is a geo file plus an
 * optional matching disputed-border file - the low tier needs its own borders
 * because at dp 3.5% the country outlines drift far enough that the base tier's
 * dp-20% overlay no longer occludes the solid stroke along lines like Kashmir.
 * `null` means "use the base tier", nothing to fetch. Fetches are async so a
 * 1.27 MB gzipped hi-res file (4.15 MB raw) never blocks page load. Module-level
 * cache fetches each file once per page regardless of how many times a viewer
 * flips quality.
 */
export interface MapDetailTier {
  geo: string
  borders: string | null
}

export interface DetailGeometry {
  countries: Map<string, string>
  borders: string | null
}

const cache = new Map<string, Promise<DetailGeometry>>()

interface CountryProps {
  name?: string
}

async function fetchDetail(
  tier: MapDetailTier,
  fit: { scale: number; translate: [number, number] },
): Promise<DetailGeometry> {
  // Pin to base tier's constants; letting this tier fitExtent would resize and
  // shift the map, desyncing city dots, markers, and arcs placed by base
  // tier's project().
  const path = geoPath(geoNaturalEarth1().scale(fit.scale).translate(fit.translate))

  // Parallel, same as useMapGeometry: the borders fetch adds no latency.
  const [res, bres] = await Promise.all([
    fetch(tier.geo),
    tier.borders ? fetch(tier.borders) : Promise.resolve(null),
  ])
  if (!res.ok) throw new Error(`detailed map failed to load (${res.status})`)
  if (bres && !bres.ok) throw new Error(`detailed border lines failed to load (${bres.status})`)

  const topology = (await res.json()) as Topology<{
    countries: GeometryCollection<CountryProps>
  }>
  const countries = new Map<string, string>()
  const features = (feature(topology, topology.objects.countries) as FeatureCollection<
    Geometry,
    CountryProps
  >).features as Feature<Geometry, CountryProps>[]
  for (const f of features) {
    const d = path(f)
    if (d) countries.set(String(f.id), d)
  }

  let borders: string | null = null
  if (bres) {
    const btop = (await bres.json()) as Topology<{ borders: GeometryCollection }>
    borders = (feature(btop, btop.objects.borders) as FeatureCollection<Geometry>).features
      .map((f) => path(f))
      .filter(Boolean)
      .join('')
  }

  return { countries, borders }
}

/**
 * Returns `{ countries, borders }` for the active tier, empty/null until it
 * loads. Binds `:d="detail.countries.get(c.id) ?? c.d"` (and the disputed
 * paths to `detail.borders ?? geometry.disputedBorders`) to swap path data
 * without remounting. `threshold` is per-tier: a coarser tier applies at
 * every zoom (threshold 0 - fewer vertices help most at k=1, and most of all
 * on the phones `enabled` would otherwise exclude), while a finer tier only
 * earns its bytes once the base tier's sub-pixel vertex spacing starts to
 * show (threshold 3). `enabled` gates the fetch entirely.
 */
export function useMapDetail(
  k: Ref<number>,
  fit: { scale: number; translate: [number, number] },
  opts: {
    threshold?: () => number
    enabled?: () => boolean
    tier: () => MapDetailTier | null
  },
): ShallowRef<DetailGeometry> {
  const empty: DetailGeometry = { countries: new Map<string, string>(), borders: null }
  const loaded = shallowRef<DetailGeometry>(empty)
  const threshold = () => opts.threshold?.() ?? 3

  // Keyed on tier.geo: switching quality keeps whatever was already fetched, so
  // going high -> regular -> high does not refetch either tier.
  watch(
    [k, () => opts.tier()],
    ([v, tier]) => {
      if (!tier || v < threshold()) return
      if (opts.enabled && !opts.enabled()) return
      const geo = tier.geo
      const hit = cache.get(geo) ?? fetchDetail(tier, fit)
      cache.set(geo, hit)
      hit
        .then((d) => {
          // A slow fetch may land after the viewer switched away from it.
          const active = opts.tier()
          if (active && active.geo === geo) loaded.value = d
        })
        .catch((err) => {
          cache.delete(geo)
          console.warn('map detail tier failed to load', err)
        })
    },
    { immediate: true },
  )

  // Below threshold, extra vertices are invisible but cost a re-raster on
  // every pan. Only apply a fetched tier once it is actually in range.
  return computed(() =>
    k.value >= threshold() && opts.tier() ? loaded.value : empty,
  ) as ShallowRef<DetailGeometry>
}
