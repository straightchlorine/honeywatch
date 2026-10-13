import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountWithProviders } from '../../helpers/mount'
import ErrorBoundary from '@/components/base/ErrorBoundary.vue'

const boom = ref(true)
const Child = defineComponent({
  setup() {
    return () => {
      if (boom.value) throw new Error('bad\x07message')
      return h('div', { class: 'recovered' }, 'ok')
    }
  },
})

// A functional child that throws whatever value it is given.
function throwing(value: unknown) {
  return () => {
    throw value
  }
}

const routes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/broken', component: { template: '<div />' } },
]

describe('ErrorBoundary', () => {
  // Unmounted in afterEach so a failed assertion cannot leave attached DOM behind.
  let attached: { unmount: () => void } | undefined

  beforeEach(() => {
    boom.value = true
  })

  afterEach(() => {
    attached?.unmount()
    attached = undefined
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders slot content when there is no error', () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h('div', { class: 'ok' }, 'fine') },
    })
    expect(w.find('.ok').exists()).toBe(true)
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('catches a child error, sanitizes the message, and recovers on reset', async () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h(Child) },
    })
    await nextTick()

    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.text()).not.toContain('\x07')
    expect(w.text()).toContain('badmessage')

    boom.value = false
    await w.get('button').trigger('click')
    await nextTick()
    expect(w.find('.recovered').exists()).toBe(true)
  })

  it('titles the alert as a heading and moves focus to the retry button', async () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h(Child) },
      attachTo: document.body,
    })
    attached = w
    await flushPromises()

    expect(w.get('h1').text()).toBe('Something went wrong')
    expect(document.activeElement).toBe(w.get('button').element)
  })

  it('unwraps an API error envelope instead of showing [object Object]', async () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h(throwing({ message: 'api failed' })) },
    })
    await nextTick()

    expect(w.get('.boundary-message').text()).toBe('api failed')
    expect(w.text()).not.toContain('[object Object]')
  })

  it('truncates long messages to 500 characters plus an ellipsis', async () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h(throwing(new Error('x'.repeat(600)))) },
    })
    await nextTick()

    const text = w.get('.boundary-message').text()
    expect(text).toHaveLength(503)
    expect(text.endsWith('...')).toBe(true)
  })

  it('offers a way home that leaves the failing route before it recovers', async () => {
    const w = mountWithProviders(ErrorBoundary, { slots: { default: () => h(Child) } }, routes)
    await w.vm.$router.push('/broken')
    await nextTick()
    expect(w.get('[role="alert"]').text()).toContain('Something went wrong')

    const push = vi.spyOn(w.vm.$router, 'push')
    boom.value = false
    await w.get('a.boundary-link').trigger('click')
    await flushPromises()
    expect(push).toHaveBeenCalledWith('/')
    expect(w.vm.$route.path).toBe('/')
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.find('.recovered').exists()).toBe(true)
  })

  it.each([
    ['ctrl', { ctrlKey: true }],
    ['cmd', { metaKey: true }],
    ['shift', { shiftKey: true }],
    ['alt', { altKey: true }],
    ['middle', { button: 1 }],
  ])('leaves a %s-click on the way-home link to the browser', async (_name, init) => {
    const w = mountWithProviders(ErrorBoundary, { slots: { default: () => h(Child) } }, routes)
    await w.vm.$router.push('/broken')
    await nextTick()

    const push = vi.spyOn(w.vm.$router, 'push')
    const ev = new MouseEvent('click', { bubbles: true, cancelable: true, ...init })
    w.get('a.boundary-link').element.dispatchEvent(ev)
    await flushPromises()

    expect(ev.defaultPrevented).toBe(false)
    expect(push).not.toHaveBeenCalled()
    expect(w.find('[role="alert"]').exists()).toBe(true)
  })

  it('hard-navigates home when the in-app navigation fails', async () => {
    const assign = vi.fn()
    const w = mountWithProviders(ErrorBoundary, { slots: { default: () => h(Child) } }, routes)
    await w.vm.$router.push('/broken')
    await nextTick()

    vi.spyOn(w.vm.$router, 'push').mockRejectedValueOnce(new Error('chunk failed to load'))
    vi.stubGlobal('location', { assign })
    await w.get('a.boundary-link').trigger('click')
    await flushPromises()

    expect(assign).toHaveBeenCalledWith('/')
  })
})
