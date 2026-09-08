import { describe, expect, it } from 'vitest'

import { clampView, easeOutCubic, zoomAtMath } from '@/composables/usePanZoom'

// The real map viewBox (useMapGeometry's WIDTH/HEIGHT).
const W = 1600
const H = 780

describe('easeOutCubic', () => {
  it('interpolates [0,1] with ease-out curve: fast start, slow end', () => {
    expect(easeOutCubic(0)).toBe(0)
    expect(easeOutCubic(1)).toBe(1)
    // Midpoint should be >0.5 because ease-out starts fast.
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5)
  })
})

describe('zoomAtMath', () => {
  it('scales k by the factor, clamped to [minK, maxK]', () => {
    const s = { k: 1, tx: 0, ty: 0 }
    expect(zoomAtMath(s, 0, 0, 2, 1, 10).k).toBe(2)
    expect(zoomAtMath(s, 0, 0, 0.1, 1, 10).k).toBe(1) // clamped to minK
    expect(zoomAtMath({ k: 9, tx: 0, ty: 0 }, 0, 0, 5, 1, 10).k).toBe(10) // clamped to maxK
  })

  it('keeps the cursor point fixed under the zoom (zoom-at-cursor)', () => {
    // Zooming in at (px, py) must leave that point's screen position unchanged.
    const s = { k: 1, tx: 0, ty: 0 }
    const px = 50
    const py = 80
    const next = zoomAtMath(s, px, py, 2, 1, 10)
    const sceneX = (px - s.tx) / s.k
    const sceneY = (py - s.ty) / s.k
    expect(next.tx + sceneX * next.k).toBeCloseTo(px)
    expect(next.ty + sceneY * next.k).toBeCloseTo(py)
  })

  it('leaves translation bounds to clampView', () => {
    // Zooming all the way out lands on minK, where the legal pan interval is
    // a single point, so the view ends up home.
    const next = zoomAtMath({ k: 5, tx: 120, ty: 40 }, 50, 50, 0.01, 1, 10)
    expect(next.k).toBe(1)
    expect(next.tx).not.toBe(0)
    expect(clampView(next, W, H, 1, 10)).toEqual({ k: 1, tx: 0, ty: 0 })
  })
})

describe('clampView', () => {
  it('pins the view home at min zoom', () => {
    // k = minK: the scene exactly fills the viewBox, so (0,0) is the only
    // translation that keeps it covered - dragging at rest must not move it.
    expect(clampView({ k: 1, tx: 5000, ty: -3000 }, W, H, 1, 16)).toEqual({ k: 1, tx: 0, ty: 0 })
  })

  it('stops a drag at the edge of the world', () => {
    // Legal interval per axis is [size * (1 - k), 0]; k = 4 gives x [-4800, 0]
    // and y [-2340, 0]. Overshoot in either direction sticks to the edge.
    expect(clampView({ k: 4, tx: 900, ty: 900 }, W, H, 1, 16)).toEqual({ k: 4, tx: 0, ty: 0 })
    expect(clampView({ k: 4, tx: -99999, ty: -99999 }, W, H, 1, 16)).toEqual({
      k: 4,
      tx: -4800,
      ty: -2340,
    })
  })

  it('leaves an in-bounds view untouched', () => {
    const s = { k: 4, tx: -1000, ty: -500 }
    expect(clampView(s, W, H, 1, 16)).toEqual(s)
  })

  it('sanitises a persisted view (sessionStorage is hand-editable)', () => {
    expect(clampView({ k: 999, tx: 0, ty: 0 }, W, H, 1, 16).k).toBe(16)
    expect(clampView({ k: 8, tx: 9e9, ty: 9e9 }, W, H, 1, 16)).toEqual({ k: 8, tx: 0, ty: 0 })
    expect(clampView({ k: NaN, tx: NaN, ty: NaN }, W, H, 1, 16)).toEqual({ k: 1, tx: 0, ty: 0 })
  })
})
