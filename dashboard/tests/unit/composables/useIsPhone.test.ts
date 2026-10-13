import { defineComponent, h } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { useIsPhone } from '@/composables/useIsPhone'
import { LIST_PHONE_MQ } from '@/utils/breakpoints'

function fakeMql(matches: boolean) {
  let listener: ((e: MediaQueryListEvent) => void) | undefined
  const mql = {
    matches,
    addEventListener: vi.fn((_: string, fn: (e: MediaQueryListEvent) => void) => (listener = fn)),
    removeEventListener: vi.fn(),
  }
  return { mql, fire: (m: boolean) => listener?.({ matches: m } as MediaQueryListEvent) }
}

function mountProbe() {
  let phone!: ReturnType<typeof useIsPhone>
  const w = mount(
    defineComponent({
      setup() {
        phone = useIsPhone()
        return () => h('div')
      },
    }),
  )
  return { w, phone }
}

afterEach(() => vi.unstubAllGlobals())

describe('useIsPhone', () => {
  it('is false when matchMedia is unavailable', () => {
    vi.stubGlobal('matchMedia', undefined)
    expect(mountProbe().phone.value).toBe(false)
  })

  it('reads the phone query and follows change events', () => {
    const { mql, fire } = fakeMql(true)
    const mm = vi.fn(() => mql)
    vi.stubGlobal('matchMedia', mm)
    const { phone } = mountProbe()
    expect(mm).toHaveBeenCalledWith(LIST_PHONE_MQ)
    expect(phone.value).toBe(true)
    fire(false)
    expect(phone.value).toBe(false)
  })

  it('removes its listener on unmount', () => {
    const { mql } = fakeMql(false)
    vi.stubGlobal('matchMedia', () => mql)
    mountProbe().w.unmount()
    const listener = mql.addEventListener.mock.calls[0]?.[1]
    expect(mql.removeEventListener).toHaveBeenCalledTimes(1)
    expect(mql.removeEventListener).toHaveBeenCalledWith('change', listener)
  })
})
