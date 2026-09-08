/**
 * Country scope validation regex, shared by views to prevent drift on valid country codes.
 */
import { computed, type ComputedRef } from 'vue'
import { useRoute } from 'vue-router'

/** ISO 3166-1 alpha-2: exactly two ASCII letters. */
const ALPHA2 = /^[A-Za-z]{2}$/

export function isAlpha2(code: string | null | undefined): boolean {
  return typeof code === 'string' && ALPHA2.test(code)
}

export interface CountryFilter {
  /** Validated, upper-cased ?country=XX; '' when absent or malformed. */
  country: ComputedRef<string>
  /** `{ country: 'XX' }` when scoped, `{}` otherwise; spread into query params. */
  countryQuery: ComputedRef<{ country?: string }>
}

/** Validates ?country=XX param; read-only as each view manages its own URL updates. */
export function useCountryFilter(): CountryFilter {
  const route = useRoute()

  const country = computed(() => {
    const c = route.query.country
    return typeof c === 'string' && ALPHA2.test(c) ? c.toUpperCase() : ''
  })
  const countryQuery = computed(() => (country.value ? { country: country.value } : {}))

  return { country, countryQuery }
}
