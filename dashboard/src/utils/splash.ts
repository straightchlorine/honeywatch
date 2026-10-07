/**
 * Loading splash (#hw-splash in index.html) that covers the page until the app has
 * rendered. It animates in pure CSS because the CSP forbids inline script; this module
 * only decides when and how it leaves.
 */

const SPLASH_ID = 'hw-splash'
const DONE_EVENT = 'hw-splash-done'
// A splash visible for less than this just fades out. The slower exit, the hexagon
// reveal in index.html (560ms), is not worth it after such a short wait.
const FAST_MS = 500
// Removes the splash if `animationend` never arrives; longer than the 560ms slowest exit.
const REMOVE_AFTER_MS = 900
// While <html> has this attribute, WorldMap plays the Helsinki ring: a hexagon outline
// that expands and fades on the honeypot marker. Must outlast its 250ms delay + 760ms run.
const PING_ATTR = 'data-hw-exit'
const PING_MS = 1200

let started = false

/**
 * Start the exit once the page has content (or an error) to show. Safe to call more
 * than once; does nothing when there is no splash.
 */
export function exitSplash(): void {
  const el = document.getElementById(SPLASH_ID)
  if (started || !el) return
  started = true

  const remove = (): void => {
    if (!el.isConnected) return
    el.remove()
    window.dispatchEvent(new Event(DONE_EVENT))
  }

  // Wait two frames: the first renders the page behind the splash (layout, the map), so
  // the exit animation does not start on that expensive frame. Frames do not run in a
  // hidden tab, so a visitor who switched away sees the exit when they come back.
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      // index.html fades the splash out by itself after 12s. If that already happened, just
      // remove it: starting the exit animation would bring it back at full opacity.
      if (parseFloat(getComputedStyle(el).opacity) < 1) return remove()
      // How long the splash has been visible, read from its only animation (the 12s
      // failsafe, which starts at first paint). performance.now() also counts the HTML
      // download, so it is only the fallback (jsdom has no getAnimations).
      const shown = Number(el.getAnimations?.()[0]?.currentTime ?? performance.now())
      if (shown < FAST_MS) el.setAttribute('data-fast', '')
      el.setAttribute('data-state', 'exit')
      el.setAttribute('aria-hidden', 'true')
      el.addEventListener('animationend', (e) => {
        if (e.target === el && e.animationName === 'hw-x-gone') remove()
      })
      setTimeout(remove, REMOVE_AFTER_MS)
      // Set in the same frame as data-state so the Helsinki ring is timed against the
      // hexagon reveal. Fast loads only fade, so they skip it. Removed again so a later
      // visit to Overview does not replay it. No reduced-motion check is needed here:
      // WorldMap only animates the ring when motion is allowed.
      if (!el.hasAttribute('data-fast')) {
        document.documentElement.setAttribute(PING_ATTR, '')
        setTimeout(() => document.documentElement.removeAttribute(PING_ATTR), PING_MS)
      }
    }),
  )
}

/**
 * Run `fn` once the splash is gone (immediately if it already is). Returns a function
 * that cancels the wait.
 */
export function afterSplash(fn: () => void): () => void {
  if (!document.getElementById(SPLASH_ID)) {
    fn()
    return () => {}
  }
  window.addEventListener(DONE_EVENT, fn, { once: true })
  return () => window.removeEventListener(DONE_EVENT, fn)
}
