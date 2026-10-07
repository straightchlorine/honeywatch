import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Module state (the once-flag) is per import, so each test loads a fresh copy.
async function load() {
  vi.resetModules()
  return import('@/utils/splash')
}

function mountSplash(): HTMLElement {
  const el = document.createElement('div')
  el.id = 'hw-splash'
  document.body.appendChild(el)
  return el
}

function endAnimation(el: HTMLElement, name: string): void {
  const e = new Event('animationend')
  Object.defineProperty(e, 'animationName', { value: name })
  el.dispatchEvent(e)
}

describe('splash', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // exitSplash waits two animation frames; run them immediately.
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0)
      return 0
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    document.body.innerHTML = ''
    document.documentElement.removeAttribute('data-hw-exit')
  })

  it('is a no-op when index.html did not provide the splash (jsdom, tests)', async () => {
    const { exitSplash, afterSplash } = await load()
    expect(() => exitSplash()).not.toThrow()
    const fn = vi.fn()
    afterSplash(fn)
    expect(fn).toHaveBeenCalledOnce()
  })

  it('waits two animation frames, so the exit does not start on the frame that renders the map', async () => {
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))
    const flushFrame = () => frames.splice(0).forEach((cb) => cb(0))
    const { exitSplash } = await load()
    const el = mountSplash()
    exitSplash()
    flushFrame()
    expect(el.hasAttribute('data-state')).toBe(false)
    flushFrame()
    expect(el.getAttribute('data-state')).toBe('exit')
  })

  it('exits once, removes on animationend, and announces it', async () => {
    const { exitSplash } = await load()
    const el = mountSplash()
    const done = vi.fn()
    window.addEventListener('hw-splash-done', done)
    vi.spyOn(performance, 'now').mockReturnValue(2000)

    exitSplash()
    exitSplash()
    expect(el.getAttribute('data-state')).toBe('exit')
    expect(el.hasAttribute('data-fast')).toBe(false)
    expect(el.getAttribute('aria-hidden')).toBe('true')

    endAnimation(el, 'hw-x-fade') // only the splash's own exit animation may remove it
    expect(el.isConnected).toBe(true)
    endAnimation(el, 'hw-x-gone')
    expect(el.isConnected).toBe(false)
    vi.advanceTimersByTime(1000) // the 900ms backup timer must not fire the done event again
    expect(done).toHaveBeenCalledOnce()
    window.removeEventListener('hw-splash-done', done)
  })

  it('takes the crossfade path when the splash has been up under 500ms', async () => {
    const { exitSplash } = await load()
    const el = mountSplash()
    vi.spyOn(performance, 'now').mockReturnValue(120)
    exitSplash()
    expect(el.hasAttribute('data-fast')).toBe(true)
  })

  it("times the splash on its own CSS clock, not the page's", async () => {
    const { exitSplash } = await load()
    const el = mountSplash()
    // Slow HTML: the page is 2s old, but the splash has only been animating for 450ms.
    vi.spyOn(performance, 'now').mockReturnValue(2000)
    Object.assign(el, { getAnimations: () => [{ currentTime: 450 }] })
    exitSplash()
    expect(el.hasAttribute('data-fast')).toBe(true)
  })

  it('marks <html> for the Helsinki ring only on the hexagon-reveal exit, and clears it', async () => {
    const { exitSplash } = await load()
    mountSplash()
    vi.spyOn(performance, 'now').mockReturnValue(2000)
    exitSplash()
    expect(document.documentElement.hasAttribute('data-hw-exit')).toBe(true)
    vi.advanceTimersByTime(1199)
    expect(document.documentElement.hasAttribute('data-hw-exit')).toBe(true)
    vi.advanceTimersByTime(2)
    expect(document.documentElement.hasAttribute('data-hw-exit')).toBe(false)
  })

  it('skips the Helsinki ring on the fast fade-out', async () => {
    const { exitSplash } = await load()
    mountSplash()
    vi.spyOn(performance, 'now').mockReturnValue(120)
    exitSplash()
    expect(document.documentElement.hasAttribute('data-hw-exit')).toBe(false)
  })

  it('removes the node by timer when animationend never fires', async () => {
    const { exitSplash } = await load()
    const el = mountSplash()
    exitSplash()
    vi.advanceTimersByTime(899)
    expect(el.isConnected).toBe(true)
    vi.advanceTimersByTime(2)
    expect(el.isConnected).toBe(false)
  })

  it('removes it without replaying the exit when the CSS failsafe already faded it', async () => {
    const { exitSplash } = await load()
    const el = mountSplash()
    el.style.opacity = '0'
    exitSplash()
    expect(el.isConnected).toBe(false)
    expect(el.hasAttribute('data-state')).toBe(false)
  })

  it('afterSplash waits for the done event and can be cancelled', async () => {
    const { afterSplash } = await load()
    const el = mountSplash()
    const kept = vi.fn()
    const cancelled = vi.fn()
    afterSplash(kept)
    afterSplash(cancelled)()
    expect(kept).not.toHaveBeenCalled()
    el.remove()
    window.dispatchEvent(new Event('hw-splash-done'))
    expect(kept).toHaveBeenCalledOnce()
    expect(cancelled).not.toHaveBeenCalled()
  })
})
