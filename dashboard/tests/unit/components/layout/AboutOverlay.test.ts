import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AboutOverlay from '@/components/layout/AboutOverlay.vue'

const SEEN_KEY = 'hw-seen-about'

function mountSplash(): HTMLElement {
  const el = document.createElement('div')
  el.id = 'hw-splash'
  document.body.appendChild(el)
  return el
}

// What splash.ts does when the splash leaves: remove the node, then announce it.
function splashGone(el: HTMLElement): void {
  el.remove()
  window.dispatchEvent(new Event('hw-splash-done'))
}

describe('AboutOverlay first visit', () => {
  afterEach(() => {
    localStorage.clear()
    document.body.innerHTML = ''
  })

  it('opens only once the loading splash is gone, and only then counts the visit', async () => {
    const splash = mountSplash()
    const w = mount(AboutOverlay)
    await nextTick()
    expect(w.find('[role="dialog"]').exists()).toBe(false)
    expect(localStorage.getItem(SEEN_KEY)).toBeNull()

    splashGone(splash)
    await nextTick()
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    expect(localStorage.getItem(SEEN_KEY)).toBe('1')
    // The map credits are always shown, not behind a click.
    expect(w.find('a[href="https://www.naturalearthdata.com"]').text()).toBe('Natural Earth')
    expect(w.text()).toContain('GeoLite2 data created by MaxMind')
    expect(w.find('a[href="https://www.maxmind.com"]').text()).toBe('MaxMind')
    w.unmount()
  })

  it('stays closed if it unmounts before the splash leaves', async () => {
    const splash = mountSplash()
    const w = mount(AboutOverlay)
    w.unmount()
    splashGone(splash)
    await nextTick()
    // The visit was never shown, so the card must still appear next time.
    expect(localStorage.getItem(SEEN_KEY)).toBeNull()
  })

  it('a keypress inside the card holds the first-visit auto-dismiss open', async () => {
    vi.useFakeTimers()
    const w = mount(AboutOverlay, { attachTo: document.body })
    window.dispatchEvent(new Event('hw-splash-done'))
    await nextTick()
    await w.find('.intro-card').trigger('keydown', { key: 'ArrowDown' })
    vi.advanceTimersByTime(6000)
    await nextTick()
    expect(w.find('[role="dialog"]').exists()).toBe(true)
    w.unmount()
    vi.useRealTimers()
  })
})
