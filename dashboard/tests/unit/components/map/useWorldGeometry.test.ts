import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadWorldGeometry } from '@/components/map/useWorldGeometry'

// Minimal valid TopoJSON: one square "country" with a zero-padded id, no
// transform (arcs are absolute lon/lat). Exercises the feature/mesh/project
// pipeline without shipping the 100KB asset into the test.
const TINY_TOPOLOGY = {
  type: 'Topology',
  arcs: [
    [
      [0, 0],
      [0, 30],
      [40, 30],
      [40, 0],
      [0, 0],
    ],
  ],
  objects: {
    countries: {
      type: 'GeometryCollection',
      geometries: [{ type: 'Polygon', id: '004', arcs: [[0]], properties: { name: 'Testland' } }],
    },
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('loadWorldGeometry', () => {
  it('projects TopoJSON into SVG paths keyed by string ISO id', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(TINY_TOPOLOGY) }),
    )

    const geo = await loadWorldGeometry('/geo/test.json')

    expect(geo.width).toBe(975)
    expect(geo.height).toBeGreaterThan(0)
    expect(geo.sphere).toMatch(/^M/)
    expect(geo.countries).toHaveLength(1)
    expect(geo.countries[0]).toMatchObject({ id: '004', name: 'Testland' })
    expect(geo.countries[0]!.d).toMatch(/^M/)
  })

  it('throws on a failed fetch', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await expect(loadWorldGeometry('/geo/missing.json')).rejects.toThrow(/404/)
  })
})
