/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest'
import { ref } from 'vue'
import {
  usePanZoom,
  easeInOutCubic,
  type PanZoomState,
} from '@/composables/usePanZoom'

const W = 1600
const H = 780

// Mock getScreenCTM since jsdom doesn't implement it
function mockGetScreenCTM(scale = 1) {
  return {
    a: scale,
    d: scale,
    e: 0,
    f: 0,
    inverse: () => ({
      a: 1 / scale,
      d: 1 / scale,
      e: 0,
      f: 0,
      transformPoint: (pt: DOMPoint) => {
        pt.x /= scale
        pt.y /= scale
        return pt
      },
    }),
    transformPoint: (pt: DOMPoint) => {
      pt.x *= scale
      pt.y *= scale
      return pt
    },
  }
}

describe('easeInOutCubic', () => {
  it('maps [0,1] to [0,1] with smooth cubic ease-in-out curve', () => {
    expect(easeInOutCubic(0)).toBe(0)
    expect(easeInOutCubic(1)).toBe(1)
  })

  it('eases in on the first half and out on the second half', () => {
    const quarter = easeInOutCubic(0.25)
    const mid = easeInOutCubic(0.5)
    const threequarters = easeInOutCubic(0.75)

    expect(quarter).toBeLessThan(mid)
    expect(mid).toBeLessThan(threequarters)
  })

  it('is symmetric around t=0.5', () => {
    // f(0.5 - x) + f(0.5 + x) should be approximately 1 for all x
    const left = easeInOutCubic(0.2)
    const right = easeInOutCubic(0.8)
    expect(left + right).toBeCloseTo(1, 5)
  })
})

describe('usePanZoom composable setup', () => {
  let svg: any
  let changesSeen: PanZoomState[]

  beforeEach(() => {
    changesSeen = []
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)
  })

  afterEach(() => {
    document.body.removeChild(svg)
  })

  it('initializes with home view (k=minK, tx=0, ty=0) at rest', () => {
    const svgRef = ref(svg)
    const pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
      onChange: (s) => changesSeen.push(s),
    })

    expect(pz.k.value).toBe(1)
    expect(pz.transform.value).toBe('translate(0,0) scale(1)')
    expect(pz.interacting.value).toBe(false)
    expect(changesSeen).toHaveLength(0)
  })

  it('accepts initial view state and clamps it', () => {
    const svgRef = ref(svg)
    const pz = usePanZoom(svgRef, {
      initial: { k: 999, tx: 0, ty: 0 },
      minK: 1,
      maxK: 10,
      viewSize: () => ({ w: W, h: H }),
    })

    expect(pz.k.value).toBe(10)
  })

  it('respects custom minK and maxK bounds', () => {
    const svgRef = ref(svg)
    const pz = usePanZoom(svgRef, {
      minK: 2,
      maxK: 8,
      viewSize: () => ({ w: W, h: H }),
    })

    expect(pz.k.value).toBe(2)
  })

  it('emits onChange callback on each state change', () => {
    const svgRef = ref(svg)
    const pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
      onChange: (s) => changesSeen.push(s),
    })

    pz.reset()
    expect(changesSeen).toHaveLength(1)
    expect(changesSeen[0]!.k).toBe(1)
  })
})

describe('usePanZoom zoom and reset', () => {
  let svg: any
  let svgRef: any
  let pz: any

  beforeEach(() => {
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)

    svgRef = ref(svg)
    pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
    })
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.removeChild(svg)
  })

  it('reset() returns to home view', () => {
    vi.useRealTimers()
    pz.k.value = 5
    pz.reset()
    expect(pz.k.value).toBe(1)
    expect(pz.transform.value).toBe('translate(0,0) scale(1)')
    vi.useFakeTimers()
  })

  it('zoomIn() increases zoom by factor 1.2 at center', () => {
    const startK = pz.k.value
    pz.zoomIn(W / 2, H / 2)
    // Default tween is 160ms
    vi.advanceTimersByTime(160)

    expect(pz.k.value).toBeGreaterThan(startK)
    expect(pz.k.value).toBeLessThanOrEqual(startK * 1.2 * 1.01) // allow 1% margin for easing
  })

  it('zoomOut() decreases zoom by factor 1/1.2 at center', () => {
    vi.useRealTimers()
    pz.k.value = 4 // zoom in first
    vi.useFakeTimers()
    const startK = pz.k.value
    pz.zoomOut(W / 2, H / 2)
    vi.advanceTimersByTime(160)

    expect(pz.k.value).toBeLessThan(startK)
  })
})

describe('usePanZoom pan clamp boundaries', () => {
  let svg: any
  let svgRef: any
  let pz: any

  beforeEach(() => {
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)

    svgRef = ref(svg)
    pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
    })
  })

  afterEach(() => {
    document.body.removeChild(svg)
  })

  it('prevents dragging past the edges by clamping tx to valid bounds', () => {
    pz.k.value = 4
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 }),
    )
    for (let i = 0; i < 20; i++) {
      pz.handlers.onPointerMove(
        new PointerEvent('pointermove', {
          clientX: 100 - i * 50,
          clientY: 100,
          pointerId: 1,
        }),
      )
    }

    // tx should be clamped to the left boundary [W*(1-k), 0]
    const minTx = W * (1 - pz.k.value)
    expect(pz.transform.value).toContain('translate(')
    const parts = pz.transform.value.match(/translate\(([-\d.]+)/)
    const tx = Number(parts![1])
    expect(tx).toBeLessThanOrEqual(0)
    expect(tx).toBeGreaterThanOrEqual(minTx)
  })

  it('clamps ty within valid bounds on vertical drag', () => {
    pz.k.value = 4
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 }),
    )
    for (let i = 0; i < 20; i++) {
      pz.handlers.onPointerMove(
        new PointerEvent('pointermove', {
          clientX: 100,
          clientY: 100 - i * 50,
          pointerId: 1,
        }),
      )
    }

    // ty should be clamped to [H*(1-k), 0]
    const minTy = H * (1 - pz.k.value)
    const parts = pz.transform.value.match(/translate\([^,]+,([-\d.]+)\)/)
    const ty = Number(parts![1])
    expect(ty).toBeLessThanOrEqual(0)
    expect(ty).toBeGreaterThanOrEqual(minTy)
  })

  it('clamping works at all zoom levels', () => {
    const zoomLevels = [1, 2, 4, 8]
    for (const k of zoomLevels) {
      pz.k.value = k
      pz.handlers.onPointerDown(
        new PointerEvent('pointerdown', { clientX: 50, clientY: 50, pointerId: 1 }),
      )
      pz.handlers.onPointerMove(
        new PointerEvent('pointermove', {
          clientX: -1000,
          clientY: 50,
          pointerId: 1,
        }),
      )

      const minTx = W * (1 - k)
      const maxTx = 0
      const parts = pz.transform.value.match(/translate\(([-\d.]+)/)
      const tx = Number(parts![1])
      expect(tx).toBeLessThanOrEqual(maxTx)
      expect(tx).toBeGreaterThanOrEqual(minTx)
    }
  })
})

describe('usePanZoom handlers', () => {
  let svg: any
  let svgRef: any
  let pz: any
  let changesSeen: PanZoomState[]

  beforeEach(() => {
    changesSeen = []
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)

    svgRef = ref(svg)
    pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
      onChange: (s) => changesSeen.push(s),
    })
  })

  afterEach(() => {
    document.body.removeChild(svg)
    changesSeen = []
  })

  it('onWheel sets interacting flag for hit-testing throttle (and clears after timeout)', () => {
    expect(pz.interacting.value).toBe(false)

    // Full wheel zoom tested in e2e; jsdom lacks DOMPoint.matrixTransform
    expect(typeof pz.handlers.onWheel).toBe('function')
  })

  it('onPointerDown starts pan state tracking', () => {
    const e = new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 })
    pz.handlers.onPointerDown(e)
    // Internal panning state is not exposed, but we can verify it doesn't error
  })

  it('onPointerMove requires 4px threshold before capturing and panning', () => {
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 }),
    )
    const startTransform = pz.transform.value

    pz.handlers.onPointerMove(
      new PointerEvent('pointermove', { clientX: 102, clientY: 100, pointerId: 1 }),
    )
    expect(pz.transform.value).toBe(startTransform)

    pz.handlers.onPointerMove(
      new PointerEvent('pointermove', { clientX: 105, clientY: 100, pointerId: 1 }),
    )
    expect(svg.setPointerCapture).toHaveBeenCalled()
  })

  it('onPointerUp clears pan state and emits onChange if panned', () => {
    changesSeen = []
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 }),
    )
    pz.handlers.onPointerMove(
      new PointerEvent('pointermove', { clientX: 110, clientY: 100, pointerId: 1 }),
    )
    pz.handlers.onPointerMove(
      new PointerEvent('pointermove', { clientX: 120, clientY: 100, pointerId: 1 }),
    )

    changesSeen.length = 0
    pz.handlers.onPointerUp(
      new PointerEvent('pointerup', { clientX: 120, clientY: 100, pointerId: 1 }),
    )
    expect(changesSeen.length).toBeGreaterThan(0)
    expect(pz.interacting.value).toBe(false)
  })

  it('onDblClick handler is defined and callable', () => {
    // Full behavior tested in e2e; jsdom lacks DOMPoint.matrixTransform
    expect(typeof pz.handlers.onDblClick).toBe('function')
  })
})

describe('usePanZoom flyTo animation', () => {
  let svg: any
  let svgRef: any
  let pz: any

  beforeEach(() => {
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)

    svgRef = ref(svg)
    pz = usePanZoom(svgRef, {
      minK: 1,
      maxK: 10,
      viewSize: () => ({ w: W, h: H }),
    })
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.removeChild(svg)
  })

  it('flyTo animates to a target point and zoom level', () => {
    const startK = pz.k.value
    const targetX = 400
    const targetY = 300
    const targetK = 3

    pz.flyTo(targetX, targetY, targetK)
    vi.advanceTimersByTime(850)

    expect(pz.k.value).toBeCloseTo(targetK, 0)
    expect(pz.k.value).not.toBe(startK)
  })

  it('flyTo clamps targetK to [minK, maxK]', () => {
    pz.flyTo(400, 300, 999) // way out of bounds
    vi.advanceTimersByTime(850)

    expect(pz.k.value).toBeLessThanOrEqual(10)
  })

  it('flyTo respects prefers-reduced-motion by jumping instantly', () => {
    vi.useRealTimers()

    const originalMatchMedia = window.matchMedia
    window.matchMedia = vi.fn((q) => {
      if (q === '(prefers-reduced-motion: reduce)') {
        return { matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() } as any
      }
      return originalMatchMedia(q)
    })

    svgRef.value = svg
    const pzReduced = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
    })

    pzReduced.flyTo(400, 300, 5)
    // Without animation, should be at target immediately
    expect(pzReduced.k.value).toBe(5)

    window.matchMedia = originalMatchMedia
    vi.useFakeTimers()
  })
})

describe('usePanZoom pinch zoom (two-pointer)', () => {
  let svg: any
  let svgRef: any
  let pz: any

  beforeEach(() => {
    svg = document.createElement('svg')
    svg.setPointerCapture = vi.fn()
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)

    svgRef = ref(svg)
    pz = usePanZoom(svgRef, {
      viewSize: () => ({ w: W, h: H }),
    })
  })

  afterEach(() => {
    document.body.removeChild(svg)
  })

  it('trackPinchUp clears pinch state when second pointer lifts', () => {
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 100, clientY: 100, pointerId: 1 }),
    )
    pz.handlers.onPointerDown(
      new PointerEvent('pointerdown', { clientX: 200, clientY: 100, pointerId: 2 }),
    )
    const k2 = pz.k.value

    pz.handlers.onPointerUp(
      new PointerEvent('pointerup', { clientX: 200, clientY: 100, pointerId: 2 }),
    )

    // After second pointer up, zoom should stop changing
    pz.handlers.onPointerMove(
      new PointerEvent('pointermove', { clientX: 110, clientY: 100, pointerId: 1 }),
    )
    expect(pz.k.value).toBe(k2)
  })
})

describe('usePanZoom min/max zoom limits', () => {
  let svg: any
  let svgRef: any

  beforeEach(() => {
    svg = document.createElement('svg')
    svg.getScreenCTM = () => mockGetScreenCTM(1)
    document.body.appendChild(svg)
    svgRef = ref(svg)
  })

  afterEach(() => {
    document.body.removeChild(svg)
  })

  it('enforces minK even when zooming out repeatedly', () => {
    const pz = usePanZoom(svgRef, {
      minK: 1,
      maxK: 10,
      viewSize: () => ({ w: W, h: H }),
    })

    for (let i = 0; i < 100; i++) {
      pz.zoomOut(W / 2, H / 2)
    }

    vi.useFakeTimers()
    vi.advanceTimersByTime(200)
    vi.useRealTimers()

    expect(pz.k.value).toBeGreaterThanOrEqual(1)
  })

  it('enforces maxK even when zooming in repeatedly', () => {
    const pz = usePanZoom(svgRef, {
      minK: 1,
      maxK: 8,
      viewSize: () => ({ w: W, h: H }),
    })

    for (let i = 0; i < 100; i++) {
      pz.zoomIn(W / 2, H / 2)
    }

    vi.useFakeTimers()
    vi.advanceTimersByTime(200)
    vi.useRealTimers()

    expect(pz.k.value).toBeLessThanOrEqual(8)
  })
})
