/**
 * Tests use a real QueryClient because useStaleData reads the query cache directly.
 */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { useStaleData } from '@/composables/useStaleData'

function mountWith(client: QueryClient) {
  const seen: { stale: boolean }[] = []
  const Probe = defineComponent({
    setup() {
      const { stale } = useStaleData()
      seen.push({ get stale() { return stale.value } } as { stale: boolean })
      return () => h('span', String(stale.value))
    },
  })
  const wrapper = mount(Probe, {
    global: { plugins: [[VueQueryPlugin, { queryClient: client }]] },
  })
  return { wrapper, seen }
}

describe('useStaleData', () => {
  it('is quiet when every query is healthy', async () => {
    const client = new QueryClient()
    client.setQueryData(['ok'], { value: 1 })
    const { wrapper } = mountWith(client)
    await nextTick()
    expect(wrapper.text()).toBe('false')
  })

  it('flags an errored query, and clears when it recovers', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { wrapper } = mountWith(client)
    await nextTick()
    expect(wrapper.text()).toBe('false')

    await client
      .fetchQuery({ queryKey: ['boom'], queryFn: () => Promise.reject(new Error('down')) })
      .catch(() => {})
    await nextTick()
    expect(wrapper.text()).toBe('true')

    // The warning reflects current state, not historical failures.
    await client.fetchQuery({ queryKey: ['boom'], queryFn: () => Promise.resolve(1) })
    await nextTick()
    expect(wrapper.text()).toBe('false')
  })

  it('stays quiet while a healthy query is merely in flight', async () => {
    const client = new QueryClient()
    let release: (v: number) => void = () => {}
    const pending = client.fetchQuery({
      queryKey: ['slow'],
      queryFn: () => new Promise<number>((r) => (release = r)),
    })
    const { wrapper } = mountWith(client)
    await nextTick()
    // Pending queries alone don't warrant a warning; only failures do.
    expect(wrapper.text()).toBe('false')
    release(1)
    await pending
    await nextTick()
    expect(wrapper.text()).toBe('false')
  })

  it('unsubscribes on unmount, so an unmounted view leaves no listener', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const cache = client.getQueryCache()
    // Spy on the real subscribe rather than reading the protected listener set.
    const unsubs: ReturnType<typeof cache.subscribe>[] = []
    const realSubscribe = cache.subscribe.bind(cache)
    const seen: number[] = []
    vi.spyOn(cache, 'subscribe').mockImplementation((fn) => {
      const off = realSubscribe(fn)
      const i = unsubs.length
      const wrapped = () => {
        seen.push(i)
        off()
      }
      unsubs.push(wrapped)
      return wrapped
    })

    const { wrapper } = mountWith(client)
    await nextTick()
    expect(unsubs).toHaveLength(1)
    expect(seen).toEqual([])

    wrapper.unmount()
    expect(seen).toEqual([0])
  })
})
