import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountWithProviders } from '../helpers/mount'
import App from '@/App.vue'

const { exitSplash, revealPage } = vi.hoisted(() => ({ exitSplash: vi.fn(), revealPage: vi.fn() }))
vi.mock('@/utils/splash', () => ({ exitSplash, revealPage }))

// A view that awaits in setup, like the data views, so Suspense has something to wait for.
// The test decides when it finishes loading.
let finishLoading = () => {}
const AsyncView = defineComponent({
  async setup() {
    await new Promise<void>((r) => (finishLoading = r))
    return () => h('div', { class: 'view' }, 'loaded')
  },
})
// A view with nothing to wait for.
const PlainView = () => h('div', { class: 'plain' })

describe('App splash wiring', () => {
  // Unmounts even when an assertion fails, so one broken test cannot leak an app into the next.
  let mounted: { unmount: () => void } | undefined
  afterEach(() => {
    mounted?.unmount()
    mounted = undefined
    vi.useRealTimers()
  })

  it('exits the splash only once a view is in, and times each page change for revealPage', async () => {
    let now = 1000
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const w = mountWithProviders(App, {}, [
      { path: '/', component: AsyncView },
      { path: '/plain', component: PlainView },
    ])
    // Suspense has already resolved once, at mount, before the first navigation matched a route.
    expect(exitSplash).not.toHaveBeenCalled()

    await flushPromises() // the first navigation starts, Suspense goes pending at now = 1000
    now = 1800
    finishLoading()
    await flushPromises()
    expect(w.find('.view').exists()).toBe(true)
    expect(exitSplash).toHaveBeenCalledTimes(1)
    expect(revealPage).toHaveBeenLastCalledWith(800)

    // A view that renders at once still starts a fresh timer, so it is never revealed.
    now = 5000
    await w.vm.$router.push('/plain')
    await flushPromises()
    expect(w.find('.plain').exists()).toBe(true)
    expect(revealPage).toHaveBeenLastCalledWith(0)
  })

  it('never leaves the page-change loader up behind the error screen', async () => {
    // Fake only setTimeout: flushPromises relies on setImmediate.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    let fail = true
    const FailingView = {
      async setup() {
        await Promise.resolve()
        if (fail) throw new Error('boom')
        return () => h('div', { class: 'view' }, 'loaded')
      },
    }
    const w = mountWithProviders(App, { attachTo: document.body }, [
      { path: '/', component: PlainView },
      { path: '/boom', component: FailingView },
    ])
    mounted = w
    await flushPromises()
    await w.vm.$router.push('/boom')
    await flushPromises()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    // The error lands inside Suspense's 220ms wait; its timer must not mount the loader later.
    vi.advanceTimersByTime(300)
    await flushPromises()
    expect(w.find('.loading').exists()).toBe(false)

    fail = false
    await w.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(w.find('.view').exists()).toBe(true)
    expect(w.find('.loading').exists()).toBe(false)
  })
})
