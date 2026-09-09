import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { useMapDetail, type MapDetailTier } from '@/composables/useMapDetail'

// One unit square, same idiom as useMapGeometry.test.ts.
const TOPOLOGY = {
  type: 'Topology',
  arcs: [
    [
      [0, 0],
      [1, 0],
      [0, 1],
      [-1, 0],
      [0, -1],
    ],
  ],
  transform: { scale: [1, 1], translate: [0, 0] },
  objects: {
    countries: {
      type: 'GeometryCollection',
      geometries: [{ type: 'Polygon', id: 'UA', arcs: [[0]], properties: { name: 'Ukraine' } }],
    },
  },
}

const BORDERS = {
  type: 'Topology',
  arcs: [
    [
      [0, 0],
      [1, 1],
    ],
  ],
  transform: { scale: [1, 1], translate: [0, 0] },
  objects: {
    borders: {
      type: 'GeometryCollection',
      geometries: [{ type: 'LineString', arcs: [0], properties: {} }],
    },
  },
}

function mockFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => (url.includes('borders') ? BORDERS : TOPOLOGY),
    })),
  )
}

const FIT = { scale: 1, translate: [0, 0] as [number, number] }

// The composable caches per geo url at module scope, so each case below uses
// its own url - reusing one across `it()` blocks would read a previous
// test's cached result instead of exercising the gate logic.
describe('useMapDetail', () => {
  it('applies a threshold-0 tier at k=1, the coarse case', async () => {
    mockFetch()
    const k = ref(1)
    const tier: MapDetailTier = { geo: '/geo/case-1-low.json', borders: null }
    const detail = useMapDetail(k, FIT, { threshold: () => 0, tier: () => tier })
    await flushPromises()
    expect(detail.value.countries.get('UA')).toBeTruthy()
  })

  it('gates a threshold-3 tier until k reaches it', async () => {
    mockFetch()
    const k = ref(1)
    const tier: MapDetailTier = { geo: '/geo/case-2-detail.json', borders: null }
    const detail = useMapDetail(k, FIT, { threshold: () => 3, tier: () => tier })
    await flushPromises()
    expect(detail.value.countries.size).toBe(0)

    k.value = 3
    await flushPromises()
    expect(detail.value.countries.get('UA')).toBeTruthy()
  })

  it('fetches nothing for a null tier (the base-only case)', async () => {
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    const k = ref(5)
    const detail = useMapDetail(k, FIT, { threshold: () => 0, tier: () => null })
    await flushPromises()
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(detail.value.countries.size).toBe(0)
    expect(detail.value.borders).toBeNull()
  })

  it('carries borders when the tier declares a borders url, null otherwise', async () => {
    mockFetch()
    const k = ref(1)
    const withBorders: MapDetailTier = {
      geo: '/geo/case-4-low.json',
      borders: '/geo/case-4-borders-disputed-low.json',
    }
    const a = useMapDetail(k, FIT, { threshold: () => 0, tier: () => withBorders })
    await flushPromises()
    expect(a.value.borders).toMatch(/^M/)

    const noBorders: MapDetailTier = { geo: '/geo/case-4-detail.json', borders: null }
    const kb = ref(3)
    const b = useMapDetail(kb, FIT, { threshold: () => 3, tier: () => noBorders })
    await flushPromises()
    expect(b.value.borders).toBeNull()
  })
})
