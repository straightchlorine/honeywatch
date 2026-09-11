import { afterEach, vi } from 'vitest'

class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}

class NoopEventSource {
  readyState = 0
  url: string
  withCredentials = false
  CONNECTING = 0
  OPEN = 1
  CLOSED = 2
  onopen: ((this: EventSource, ev: Event) => unknown) | null = null
  onmessage: ((this: EventSource, ev: MessageEvent) => unknown) | null = null
  onerror: ((this: EventSource, ev: Event) => unknown) | null = null
  constructor(url: string) {
    this.url = url
  }
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true
  }
}

function buildMatchMediaStub(matches: boolean) {
  return (q: string) => ({
    matches,
    media: q,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false
    },
  })
}

if (!globalThis.matchMedia) {
  Object.defineProperty(globalThis, 'matchMedia', {
    writable: true,
    value: buildMatchMediaStub(false),
  })
}

/**
 * Override the default matchMedia stub for a test/describe block (e.g. '(hover: none)' for touch).
 * Shared so tests don't hand-roll their own.
 */
export function stubMatchMedia(matches: boolean): typeof globalThis.matchMedia {
  const stub = buildMatchMediaStub(matches) as unknown as typeof globalThis.matchMedia
  globalThis.matchMedia = stub
  return stub
}

type GlobalWithPolyfills = typeof globalThis & {
  IntersectionObserver?: unknown
  ResizeObserver?: unknown
  EventSource?: unknown
  DOMPoint?: unknown
}
const g = globalThis as GlobalWithPolyfills
// jsdom lacks these; the Noop stubs only need to exist, not be spec-complete.
g.IntersectionObserver ??= NoopObserver as unknown as typeof IntersectionObserver
g.ResizeObserver ??= NoopObserver as unknown as typeof ResizeObserver
g.EventSource ??= NoopEventSource as unknown as typeof EventSource

// jsdom lacks DOMPoint; usePanZoom builds one to map client coords to SVG space.
// Only 2D affine is implemented (all an SVGMatrix from getScreenCTM() carries);
// 3D would be untested.
if (!g.DOMPoint) {
  class DOMPointPolyfill {
    constructor(
      public x = 0,
      public y = 0,
      public z = 0,
      public w = 1,
    ) {}

    matrixTransform(m: { a: number; b: number; c: number; d: number; e: number; f: number }) {
      if (!m) return this
      return new DOMPointPolyfill(
        m.a * this.x + m.c * this.y + m.e,
        m.b * this.x + m.d * this.y + m.f,
        this.z,
        this.w,
      )
    }
  }
  g.DOMPoint = DOMPointPolyfill as unknown as typeof DOMPoint
}

interface Matrix2D {
  a: number
  b: number
  c: number
  d: number
  e: number
  f: number
}

/**
 * Build a fake SVGMatrix as returned by `svg.getScreenCTM()`. Shared so tests
 * don't hand-roll partial mocks that break DOMPoint#matrixTransform (missing b/c silently
 * causes NaN). usePanZoom expects .a/.d for scaling and .inverse().
 */
export function mockScreenCTM(matrix: Matrix2D): Matrix2D & { inverse: () => Matrix2D } {
  const { a, b, c, d, e, f } = matrix
  const det = a * d - b * c
  return {
    a,
    b,
    c,
    d,
    e,
    f,
    inverse: () => ({
      a: d / det,
      b: -b / det,
      c: -c / det,
      d: a / det,
      e: (c * f - d * e) / det,
      f: (b * e - a * f) / det,
    }),
  }
}

afterEach(() => {
  vi.clearAllMocks()
})
