import { describe, expect, it, vi } from 'vitest'

import { loadMapGeometry } from '@/components/map/useMapGeometry'

// Two unit squares, ids as scripts/gen-world-geo.mjs emits them: ISO alpha-2
// for real countries, a 3-letter Natural Earth ADM0_A3 for the areas that have
// no ISO code at all.
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
      geometries: [
        { type: 'Polygon', id: 'UA', arcs: [[0]], properties: { name: 'Ukraine' } },
        { type: 'Polygon', id: 'ESB', arcs: [[0]], properties: { name: 'Dhekelia' } },
        { type: 'Polygon', id: 'XK', arcs: [[0]], properties: {} },
      ],
    },
  },
}

// The disputed-boundary layer is a second, separate fetch, so the mock has to
// answer per URL rather than handing the same topology to both.
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

function mockFetch(ok = true): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok,
      status: ok ? 200 : 404,
      json: async () => (url.includes('borders') ? BORDERS : TOPOLOGY),
    })),
  )
}

describe('loadMapGeometry', () => {
  it('uses the alpha-2 feature id directly as the data-join key', async () => {
    mockFetch()
    const { countries } = await loadMapGeometry('/geo/countries.json')
    const ua = countries.find((c) => c.id === 'UA')
    expect(ua?.a2).toBe('UA')
    expect(ua?.name).toBe('Ukraine')
    expect(ua?.d).toBeTruthy()
  })

  it('leaves a2 null for the non-ISO areas so they stay unjoinable land', async () => {
    // Sovereign base areas (ESB), Bir Tawil and the disputed reefs have no ISO
    // alpha-2, so they carry a 3-letter ADM0_A3 id and render as inert land.
    mockFetch()
    const { countries } = await loadMapGeometry('/geo/countries.json')
    expect(countries.find((c) => c.id === 'ESB')?.a2).toBeNull()
  })

  it('keeps every id unique - WorldMap keys its country paths on it', async () => {
    mockFetch()
    const { countries } = await loadMapGeometry('/geo/countries.json')
    expect(new Set(countries.map((c) => c.id)).size).toBe(countries.length)
  })

  it('falls back to the id when a feature carries no name', async () => {
    mockFetch()
    const { countries } = await loadMapGeometry('/geo/countries.json')
    expect(countries.find((c) => c.id === 'XK')?.name).toBe('XK')
  })

  it('projects the disputed boundary lines into a single path', async () => {
    mockFetch()
    const { disputedBorders } = await loadMapGeometry('/geo/countries.json')
    expect(disputedBorders).toMatch(/^M/)
  })

  it('throws when the geometry file is missing', async () => {
    mockFetch(false)
    await expect(loadMapGeometry('/geo/countries.json')).rejects.toThrow(/404/)
  })
})
