import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref, Suspense } from 'vue'
import type { MapCountryResponse, MapCityResponse } from '@/api/generated/types.gen'
import type { MapGeometry } from '@/components/map/useMapGeometry'
import WorldMap from '@/components/map/WorldMap.vue'

interface WorldMapExposed {
  fireArc: (a2: string, lat?: number | null, lon?: number | null) => void
}

// Mock WAAPI animate() which jsdom doesn't support
const mockAnimate = () => {
  const listeners: { finish?: () => void; error?: () => void } = {}
  const animation = {
    addEventListener: (event: string, callback: () => void) => {
      if (event === 'finish') listeners.finish = callback
      if (event === 'error') listeners.error = callback
    },
    finish: () => {
      listeners.finish?.()
    },
  }

  setTimeout(() => {
    listeners.finish?.()
  }, 0)

  return animation
}

if (typeof SVGElement !== 'undefined') {
  ;(SVGElement.prototype as unknown as Record<string, unknown>).animate = function () {
    return mockAnimate()
  }
}

vi.mock('@/components/map/useMapGeometry', () => {
  const testProject = (lon: number, lat: number): [number, number] => {
    return [lon * 100 + 800, lat * 100 + 400]
  }

  return {
    loadMapGeometry: vi.fn(
      async (): Promise<MapGeometry> => {
        return Promise.resolve({
          width: 1600,
          height: 780,
          sphere: 'M0,0',
          graticule: 'M0,0L10,10',
          countries: [
            {
              id: '840',
              a2: 'US',
              name: 'United States',
              d: 'M0,0L100,0L100,100L0,100Z',
              centroid: [500, 300],
            },
          ],
          project: testProject,
          fit: { scale: 1, translate: [0, 0] as [number, number] },
          disputedBorders: '',
        })
      },
    ),
  }
})

describe('WorldMap: fireArc', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // WorldMap's async setup leaves template refs null until mounted under Suspense.
  // Built with h() since the test build is runtime-only; mirrors how OverviewView reaches fireArc.
  async function mountMap(countries: MapCountryResponse[]) {
    const map = ref<WorldMapExposed | null>(null)
    const host = defineComponent({
      render: () =>
        h(Suspense, null, {
          default: () =>
            h(WorldMap, {
              ref: map,
              countries,
              cities: [] as MapCityResponse[],
              totalSessions: 100,
            }),
        }),
    })
    const wrapper = mount(host)
    await flushPromises()
    await new Promise((r) => setTimeout(r, 100))
    await wrapper.vm.$nextTick()
    return { wrapper, map: map.value as WorldMapExposed }
  }

  const US: MapCountryResponse = { a2: 'US', ips: 50, sessions: 100, success_rate: 1.5 }

  it('exposes fireArc after geometry loads', async () => {
    const { map } = await mountMap([US])

    expect(typeof map.fireArc).toBe('function')
  })

  it('fireArc appends one dot per call', async () => {
    const { wrapper, map } = await mountMap([US])
    map.fireArc('US')

    expect(wrapper.findAll('.arc-dot')).toHaveLength(1)
  })

  // Counted synchronously: the mocked animate() fires 'finish' on the next
  // tick, which tears the dots down and would make any awaited count pass.
  it('fireArc caps concurrent dots at MAX_ARCS', async () => {
    const { wrapper, map } = await mountMap([US])
    const fireArc = map.fireArc

    fireArc('US', 1, 1)
    fireArc('US', 2, 2)
    fireArc('US', 3, 3)

    expect(wrapper.findAll('.arc-dot')).toHaveLength(2)
  })

  it('fireArc releases its slot once a dot finishes', async () => {
    const { wrapper, map } = await mountMap([US])
    map.fireArc('US', 1, 1)
    map.fireArc('US', 2, 2)
    expect(wrapper.findAll('.arc-dot')).toHaveLength(2)

    // Lets the mocked animate() fire 'finish', which tears both dots down.
    await new Promise((r) => setTimeout(r, 10))
    expect(wrapper.findAll('.arc-dot')).toHaveLength(0)

    map.fireArc('US', 3, 3)
    expect(wrapper.findAll('.arc-dot')).toHaveLength(1)
  })

  it('fireArc ignores a country it has no geometry for', async () => {
    const { wrapper, map } = await mountMap([US])
    map.fireArc('XX')

    expect(wrapper.findAll('.arc-dot')).toHaveLength(0)
  })

  it('the dot starts at the country centroid when the session has no coordinates', async () => {
    const { wrapper, map } = await mountMap([US])
    map.fireArc('US')

    // [500, 300] is the mocked geometry's US centroid.
    expect(wrapper.find('.arc-dot').attributes('transform')).toBe('translate(500 300)')
  })

  it('the dot starts at the session coordinates when geo has a city fix', async () => {
    const { wrapper, map } = await mountMap([US])
    map.fireArc('US', 3, 2)

    // testProject(lon, lat) = [lon * 100 + 800, lat * 100 + 400]
    expect(wrapper.find('.arc-dot').attributes('transform')).toBe('translate(1000 700)')
  })
})
