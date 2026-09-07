import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useQueryClient } from '@tanstack/vue-query'
import { mountWithProviders } from '../../helpers/mount'

// Mock queries; factory just needs stable key/queryFn pair.
vi.mock('@/api/queries', () => ({
  statsTopCountriesOptions: () => ({ queryKey: ['top-countries'], queryFn: async () => [] }),
}))

// Import *after* the mock is registered so the hoisted vi.mock applies.
import { useCountryOptions } from '@/composables/useCountryOptions'

const FIXTURE = [
  { country_code: 'US', country: 'United States', count: 80 },
  { country_code: 'CN', country: 'China', count: 40 },
  { country_code: 'DE', country: 'Germany', count: 12 },
]

type CountryEntry = { country_code: string | null; country: string | null; count: number }

function mountOptions(allLabel: string, data: CountryEntry[] = []) {
  let opts: ReturnType<typeof useCountryOptions> | undefined
  const Wrapper = defineComponent({
    setup() {
      const qc = useQueryClient()
      qc.setQueryData(['top-countries'], data)
      opts = useCountryOptions(allLabel)
      return () => h('div')
    },
  })
  mountWithProviders(Wrapper)
  return opts!
}

describe('useCountryOptions', () => {
  it('always places the all-countries option first with the provided label', () => {
    const opts = mountOptions('the world')
    expect(opts.value[0]).toEqual({ value: '', label: 'the world' })
  })

  it('accepts a different allLabel for a second call site', () => {
    const opts = mountOptions('All countries')
    expect(opts.value[0]).toEqual({ value: '', label: 'All countries' })
  })

  it('maps top-countries entries to {value, label, icon} with pre-seeded cache data', () => {
    const opts = mountOptions('the world', FIXTURE)
    const entries = opts.value.slice(1)
    expect(entries).toHaveLength(3)
    expect(entries[0]).toEqual({ value: 'US', label: 'United States', icon: '🇺🇸' })
    expect(entries[1]).toEqual({ value: 'CN', label: 'China', icon: '🇨🇳' })
    expect(entries[2]).toEqual({ value: 'DE', label: 'Germany', icon: '🇩🇪' })
  })

  it('filters out entries whose country_code is not a valid alpha-2', () => {
    const opts = mountOptions('the world', [
      { country_code: 'US', country: 'United States', count: 10 },
      { country_code: 'XYZ', country: 'Invalid', count: 5 },
      { country_code: null, country: 'Unknown', count: 3 },
    ])
    const entries = opts.value.slice(1)
    expect(entries).toHaveLength(1)
    expect(entries[0]!.value).toBe('US')
  })

  it('falls back to country_code as label when the country name is absent', () => {
    const opts = mountOptions('the world', [{ country_code: 'TW', country: null, count: 7 }])
    const entries = opts.value.slice(1)
    expect(entries[0]).toEqual({ value: 'TW', label: 'TW', icon: '🇹🇼' })
  })
})
