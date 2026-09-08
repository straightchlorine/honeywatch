import { computed, shallowRef, watch, type Ref, type ShallowRef } from 'vue'
import { geoNaturalEarth1, geoPath } from 'd3-geo'
import type { Feature, FeatureCollection, Geometry } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'

/**
 * Lazily load high-detail geometry when the user zooms past base tier capacity.
 * Base is simplified for fast first paint; at k=4+, missing vertices cannot be
 * recovered by reprojection. Asynchronous fetch avoids blocking page load with a
 * 1.3 MB file. Module-level cache fetches once per page.
 */
const cache = new Map<string, Promise<Map<string, string>>>()

interface CountryProps {
  name?: string
}

async function fetchDetail(
  url: string,
  fit: { scale: number; translate: [number, number] },
): Promise<Map<string, string>> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`detailed map failed to load (${res.status})`)
  const topology = (await res.json()) as Topology<{
    countries: GeometryCollection<CountryProps>
  }>
  // Pin to base tier's constants; letting this tier fitExtent would resize and shift
  // the map, desyncing city dots, markers, and arcs placed by base tier's project().
  const path = geoPath(geoNaturalEarth1().scale(fit.scale).translate(fit.translate))
  const out = new Map<string, string>()
  const features = (feature(topology, topology.objects.countries) as FeatureCollection<
    Geometry,
    CountryProps
  >).features as Feature<Geometry, CountryProps>[]
  for (const f of features) {
    const d = path(f)
    if (d) out.set(String(f.id), d)
  }
  return out
}

/**
 * Returns a map of feature id -> path, empty until the tier loads. Binds
 * `:d="detail.get(c.id) ?? c.d"` to swap path data without remounting. `enabled`
 * gates the fetch; mobile doesn't need it (base data stays sharp well past
 * practical zoom, making 1.3 MB wasteful).
 */
export function useMapDetail(
  k: Ref<number>,
  fit: { scale: number; translate: [number, number] },
  opts: { threshold?: number; enabled?: () => boolean; url: () => string | null },
): ShallowRef<Map<string, string>> {
  const loaded = shallowRef(new Map<string, string>())
  const threshold = opts.threshold ?? 3

  // Keyed on url: switching quality keeps whatever was already fetched, so
  // going high -> regular -> high does not refetch either tier.
  watch(
    [k, () => opts.url()],
    ([v, url]) => {
      if (!url || v < threshold) return
      if (opts.enabled && !opts.enabled()) return
      const hit = cache.get(url) ?? fetchDetail(url, fit)
      cache.set(url, hit)
      hit
        .then((m) => {
          // A slow fetch may land after the viewer switched away from it.
          if (opts.url() === url) loaded.value = m
        })
        .catch((err) => {
          cache.delete(url)
          console.warn('hi-res map tier failed to load', err)
        })
    },
    { immediate: true },
  )

  // Below threshold, extra vertices are invisible (~1% pixel change at k=1) but cost
  // 5x re-raster on every pan. Only use when zoomed in, even though cached.
  const empty = new Map<string, string>()
  return computed(() =>
    k.value >= threshold && opts.url() ? loaded.value : empty,
  ) as ShallowRef<Map<string, string>>
}
