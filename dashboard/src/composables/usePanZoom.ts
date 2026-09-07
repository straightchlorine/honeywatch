import { ref, computed, type Ref } from 'vue'
import { useReducedMotion } from './useReducedMotion'

export interface PanZoomState {
  k: number
  tx: number
  ty: number
}

/**
 * Pure zoom-at-cursor arithmetic, extracted so it is unit-testable: jsdom has
 * no `getScreenCTM`, so the DOM half of usePanZoom can only be covered by a
 * real e2e interaction. Bounds are not this function's job - `clampView`
 * applies them on the way into the refs.
 */
export function zoomAtMath(
  state: PanZoomState,
  px: number,
  py: number,
  factor: number,
  minK: number,
  maxK: number,
): PanZoomState {
  const nk = Math.min(maxK, Math.max(minK, state.k * factor))
  return {
    k: nk,
    tx: px - ((px - state.tx) / state.k) * nk,
    ty: py - ((py - state.ty) / state.k) * nk,
  }
}

/**
 * Clamp a candidate view: k into [minK, maxK], and the translation so the
 * scene can never be dragged off screen.
 *
 * The scene is drawn as `translate(tx,ty) scale(k)` into a `w` x `h` viewBox,
 * so it spans [tx, tx + k*w]. Covering [0, w] requires tx <= 0 and
 * tx + k*w >= w, i.e. tx in [w*(1-k), 0] (ty likewise). At k = minK = 1 that
 * interval collapses to exactly 0.
 *
 * The bounds are viewBox units, so they are aspect-independent: the svg is
 * letterboxed by the default preserveAspectRatio and the visible region is a
 * superset of the viewBox rect, so covering the rect keeps the world on screen
 * at any element aspect - no ResizeObserver, no getScreenCTM.
 *
 * The `||` fallbacks scrub NaN out of a hand-edited sessionStorage payload and
 * normalise -0 out of the transform string.
 */
export function clampView(
  s: PanZoomState,
  w: number,
  h: number,
  minK: number,
  maxK: number,
): PanZoomState {
  const k = Math.min(maxK, Math.max(minK, s.k)) || minK
  return {
    k,
    tx: Math.min(0, Math.max(w * (1 - k), s.tx)) || 0,
    ty: Math.min(0, Math.max(h * (1 - k), s.ty)) || 0,
  }
}

/**
 * Ease-out cubic: starts fast, ends slow for pleasant arrivals.
 */
export function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3)
}

/**
 * Ease-in-out cubic: smooth acceleration and deceleration.
 * Better for longer animations like city fly-to.
 */
export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/**
 * Pan/zoom for an SVG scene group. Attribute-transform based (always crisp -
 * no CSS-layer rasterization blur at high zoom).
 *
 * CRITICAL: pointer capture starts only after a 4px movement threshold.
 * Capturing on pointerdown retargets the subsequent click to the svg root,
 * which silently breaks click handlers on countries.
 */
export function usePanZoom(
  svg: Ref<SVGSVGElement | null>,
  opts: {
    minK?: number
    maxK?: number
    /** restore/persist view state, e.g. sessionStorage */
    initial?: PanZoomState
    onChange?: (s: PanZoomState) => void
    /** SVG viewBox dimensions - drives flyTo centring and the pan bounds */
    viewSize: () => { w: number; h: number }
  },
) {
  const minK = opts.minK ?? 1
  const maxK = opts.maxK ?? 10
  const k = ref(minK)
  const tx = ref(0)
  const ty = ref(0)
  /**
   * True while a gesture is in flight. Bound to a class on the svg so hit
   * testing can be suppressed for the duration: with the hi-res tier loaded,
   * hit-testing 255 complex paths per frame is the dominant cost. Measured in
   * Firefox, p90 32ms -> 21ms and max 36ms -> 23ms, with twice as many frames
   * delivered. Nothing is clickable mid-gesture anyway.
   */
  const interacting = ref(false)
  const transform = computed(() => `translate(${tx.value},${ty.value}) scale(${k.value})`)
  const reducedMotion = useReducedMotion()

  /**
   * The single write path for k/tx/ty. Every mutation - drag, wheel, pinch,
   * both tweens, flyTo, reset and the sessionStorage restore - routes through
   * here, so `grep '\.value = '` in this file returns only the three lines
   * below and the clamp invariant stays auditable.
   */
  function commit(next: PanZoomState): void {
    const { w, h } = opts.viewSize()
    const s = clampView(next, w, h, minK, maxK)
    k.value = s.k
    tx.value = s.tx
    ty.value = s.ty
  }

  // A persisted view is unvalidated input: it can be stale, out of range, or
  // hand-edited to NaN. Clamp it rather than trusting it.
  if (opts.initial) commit(opts.initial)

  const emit = (): void => opts.onChange?.({ k: k.value, tx: tx.value, ty: ty.value })

  function svgPoint(e: { clientX: number; clientY: number }): DOMPoint {
    const pt = new DOMPoint(e.clientX, e.clientY)
    return pt.matrixTransform(svg.value!.getScreenCTM()!.inverse())
  }

  function zoomAt(px: number, py: number, factor: number): void {
    commit(zoomAtMath({ k: k.value, tx: tx.value, ty: ty.value }, px, py, factor, minK, maxK))
    emit()
  }

  let panning: { x: number; y: number; tx: number; ty: number; id: number; moved: boolean } | null =
    null
  let tweenHandle: number | null = null

  function cancelTween(): void {
    if (tweenHandle !== null) {
      cancelAnimationFrame(tweenHandle)
      tweenHandle = null
    }
  }

  /**
   * Animate button/double-click zoom over ~160ms with ease-out curve.
   * Small per-frame factors preserve zoomAtMath clamping. Respects
   * prefers-reduced-motion to apply instantly if enabled.
   */
  function tweenZoomAt(px: number, py: number, targetFactor: number): void {
    if (reducedMotion.value) {
      zoomAt(px, py, targetFactor)
      return
    }

    const startTime = performance.now()
    const startState = { k: k.value, tx: tx.value, ty: ty.value }
    const finalState = zoomAtMath(startState, px, py, targetFactor, minK, maxK)
    const targetK = finalState.k

    function animateFrame(now: number): void {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / 160, 1)
      const eased = easeOutCubic(progress)

      const interpolatedK = startState.k + (targetK - startState.k) * eased
      const frameFactor = interpolatedK / startState.k

      commit(zoomAtMath(startState, px, py, frameFactor, minK, maxK))
      emit()

      if (progress < 1) {
        tweenHandle = requestAnimationFrame(animateFrame)
      } else {
        tweenHandle = null
      }
    }

    cancelTween()
    tweenHandle = requestAnimationFrame(animateFrame)
  }

  /**
   * Animate pan and zoom to center a local SVG point (x, y) at the viewport center,
   * ending at a specified zoom level. Uses ease-in-out curve over ~850ms for a smooth,
   * Google-Maps-like glide (longer than the snappy button-zoom animations).
   * Respects prefers-reduced-motion to jump instantly if enabled.
   */
  function flyTo(x: number, y: number, targetK: number): void {
    const finalK = Math.min(maxK, Math.max(minK, targetK))

    const { w, h } = opts.viewSize()
    // Clamp the target up front so the glide never fights the clamp. k and the
    // translation ride the same eased scalar and the bound is linear in k, so
    // interpolating between two in-bounds views is in bounds on every frame.
    const target = clampView({ k: finalK, tx: w / 2 - finalK * x, ty: h / 2 - finalK * y }, w, h, minK, maxK)
    const finalTx = target.tx
    const finalTy = target.ty

    if (reducedMotion.value) {
      commit(target)
      emit()
      return
    }

    cancelTween()
    const startTime = performance.now()
    const startState = { k: k.value, tx: tx.value, ty: ty.value }
    const DURATION = 850 // ms - slower, smoother glide for city fly-to

    function animateFrame(now: number): void {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / DURATION, 1)
      const eased = easeInOutCubic(progress)

      commit({
        k: startState.k + (finalK - startState.k) * eased,
        tx: startState.tx + (finalTx - startState.tx) * eased,
        ty: startState.ty + (finalTy - startState.ty) * eased,
      })
      emit()

      if (progress < 1) {
        tweenHandle = requestAnimationFrame(animateFrame)
      } else {
        tweenHandle = null
      }
    }

    tweenHandle = requestAnimationFrame(animateFrame)
  }

  // Two-pointer pinch tracking; while active, single-pointer panning is
  // suspended. Requires `touch-action: none` on the svg (CSS) or the browser
  // consumes the gesture for page zoom/scroll before pointer events fire.
  const pointers = new Map<number, { x: number; y: number }>()
  let pinchDist = 0

  function trackPinchDown(e: PointerEvent): void {
    cancelTween()
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()] as [{ x: number; y: number }, { x: number; y: number }]
      pinchDist = Math.hypot(a.x - b.x, a.y - b.y)
      panning = null
    }
  }

  function trackPinchMove(e: PointerEvent): boolean {
    if (!pointers.has(e.pointerId)) return false
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size !== 2) return false
    const [a, b] = [...pointers.values()] as [{ x: number; y: number }, { x: number; y: number }]
    const d = Math.hypot(a.x - b.x, a.y - b.y)
    if (pinchDist > 0) {
      const mid = svgPoint({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 })
      zoomAt(mid.x, mid.y, d / pinchDist)
    }
    pinchDist = d
    return true
  }

  function trackPinchUp(e: PointerEvent): void {
    pointers.delete(e.pointerId)
    pinchDist = 0
  }

  let wheelIdle: ReturnType<typeof setTimeout> | undefined
  function onWheel(e: WheelEvent): void {
    cancelTween()
    e.preventDefault()
    interacting.value = true
    clearTimeout(wheelIdle)
    wheelIdle = setTimeout(() => (interacting.value = false), 140)
    const p = svgPoint(e)
    zoomAt(p.x, p.y, Math.exp(-e.deltaY * 0.0016))
  }

  function onPointerDown(e: PointerEvent): void {
    cancelTween()
    trackPinchDown(e)
    panning = {
      x: e.clientX,
      y: e.clientY,
      tx: tx.value,
      ty: ty.value,
      id: e.pointerId,
      moved: false,
    }
  }

  function onPointerMove(e: PointerEvent): void {
    if (trackPinchMove(e)) return
    if (!panning) return
    const dx = e.clientX - panning.x
    const dy = e.clientY - panning.y
    if (!panning.moved) {
      if (Math.hypot(dx, dy) < 4) return
      panning.moved = true
      interacting.value = true
      svg.value!.setPointerCapture(panning.id)
    }
    const ctm = svg.value!.getScreenCTM()!
    commit({ k: k.value, tx: panning.tx + dx / ctm.a, ty: panning.ty + dy / ctm.d })
    // Re-anchor on the clamped result so a drag that overshoots the edge
    // responds on the way back instead of first eating the overshoot.
    panning.x = e.clientX
    panning.y = e.clientY
    panning.tx = tx.value
    panning.ty = ty.value
  }

  function onPointerUp(e: PointerEvent): void {
    trackPinchUp(e)
    if (panning?.moved) emit()
    panning = null
    interacting.value = false
  }

  function onDblClick(e: MouseEvent): void {
    const p = svgPoint(e)
    tweenZoomAt(p.x, p.y, 1.7)
  }

  const reset = (): void => {
    commit({ k: minK, tx: 0, ty: 0 })
    emit()
  }
  const zoomIn = (cx: number, cy: number): void => tweenZoomAt(cx, cy, 1.2)
  const zoomOut = (cx: number, cy: number): void => tweenZoomAt(cx, cy, 1 / 1.2)

  return {
    k,
    interacting,
    transform,
    reset,
    zoomIn,
    zoomOut,
    flyTo,
    handlers: { onWheel, onPointerDown, onPointerMove, onPointerUp, onDblClick },
  }
}
