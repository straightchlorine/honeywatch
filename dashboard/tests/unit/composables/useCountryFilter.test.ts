import { defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'
import { mountWithProviders } from '../../helpers/mount'
import { isAlpha2, useCountryFilter } from '@/composables/useCountryFilter'

// ---------------------------------------------------------------------------
// isAlpha2 — pure validation helper
// ---------------------------------------------------------------------------

describe('isAlpha2', () => {
  it('accepts exactly two ASCII letters (case-insensitive)', () => {
    expect(isAlpha2('us')).toBe(true)
    expect(isAlpha2('US')).toBe(true)
    expect(isAlpha2('Gb')).toBe(true)
  })

  it('rejects codes that are too short, too long, or non-alpha', () => {
    expect(isAlpha2('')).toBe(false)
    expect(isAlpha2('u')).toBe(false)
    expect(isAlpha2('usa')).toBe(false)
    expect(isAlpha2('1')).toBe(false)
    expect(isAlpha2('1a')).toBe(false)
    expect(isAlpha2(null)).toBe(false)
    expect(isAlpha2(undefined)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// useCountryFilter — route-aware composable
// ---------------------------------------------------------------------------

/**
 * Mount a thin wrapper that calls useCountryFilter() and exposes the result
 * through the component instance so tests can inspect it after navigation.
 */
function mountFilter() {
  let captured: ReturnType<typeof useCountryFilter> | undefined
  const Wrapper = defineComponent({
    setup() {
      captured = useCountryFilter()
      return () => h('div')
    },
  })
  const wrapper = mountWithProviders(Wrapper)
  // Captured is set synchronously during setup.
  return { wrapper, filter: captured! }
}

describe('useCountryFilter', () => {
  it('returns an empty string when ?country is absent', () => {
    const { filter } = mountFilter()
    expect(filter.country.value).toBe('')
    expect(filter.countryQuery.value).toEqual({})
  })

  it('uppercases and validates a well-formed alpha-2 code', async () => {
    const { wrapper, filter } = mountFilter()
    const router = wrapper.vm.$router
    await router.push('/?country=us')
    expect(filter.country.value).toBe('US')
    expect(filter.countryQuery.value).toEqual({ country: 'US' })
  })

  it('rejects a three-letter code and returns empty', async () => {
    const { wrapper, filter } = mountFilter()
    await wrapper.vm.$router.push('/?country=usa')
    expect(filter.country.value).toBe('')
    expect(filter.countryQuery.value).toEqual({})
  })

  it('rejects a single-digit value and returns empty', async () => {
    const { wrapper, filter } = mountFilter()
    await wrapper.vm.$router.push('/?country=1')
    expect(filter.country.value).toBe('')
  })

  it('rejects an empty string value and returns empty', async () => {
    const { wrapper, filter } = mountFilter()
    await wrapper.vm.$router.push('/?country=')
    expect(filter.country.value).toBe('')
  })
})
