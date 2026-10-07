import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountWithProviders } from '../helpers/mount'
import App from '@/App.vue'

const exitSplash = vi.hoisted(() => vi.fn())
vi.mock('@/utils/splash', () => ({ exitSplash }))

// A view that awaits in setup, like the data views, so Suspense has something to wait for.
const AsyncView = defineComponent({
  async setup() {
    await new Promise((r) => setTimeout(r, 0))
    return () => h('div', { class: 'view' }, 'loaded')
  },
})

describe('App splash wiring', () => {
  beforeEach(() => exitSplash.mockClear())

  it('ignores the mount-time resolve of the empty initial route, exits when the view is in', async () => {
    const w = mountWithProviders(App, {}, [{ path: '/', component: AsyncView }])
    // Suspense has already resolved once, at mount, before the first navigation matched a route.
    expect(exitSplash).not.toHaveBeenCalled()
    await flushPromises()
    await new Promise((r) => setTimeout(r, 5))
    await flushPromises()
    expect(w.find('.view').exists()).toBe(true)
    expect(exitSplash).toHaveBeenCalledTimes(1)
  })
})
