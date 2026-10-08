import { describe, expect, it, vi } from 'vitest'
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
})
