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

if (!globalThis.matchMedia) {
  Object.defineProperty(globalThis, 'matchMedia', {
    writable: true,
    value: (q: string) => ({
      matches: false,
      media: q,
      onchange: null,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
      dispatchEvent() {
        return false
      },
    }),
  })
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

afterEach(() => {
  vi.clearAllMocks()
})
