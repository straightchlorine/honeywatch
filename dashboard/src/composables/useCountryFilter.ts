/**
 * Country scope lives in the URL (?country=XX); empty = all countries. Shared by
 * ActivityView and SessionsView, which both read/validate/normalize the same
 * alpha-2 param. This is the single source of the validation regex so the two
 * views can never drift on what counts as a valid country code.
 */
import { computed, type ComputedRef } from 'vue'
import { useRoute } from 'vue-router'

/** ISO 3166-1 alpha-2: exactly two ASCII letters. */
const ALPHA2 = /^[A-Za-z]{2}$/

/** True when `code` is a syntactically valid alpha-2 country code. */
export function isAlpha2(code: string | null | undefined): boolean {
  return typeof code === 'string' && ALPHA2.test(code)
}

export interface CountryFilter {
  /** Validated, upper-cased ?country=XX; '' when absent or malformed. */
  country: ComputedRef<string>
  /** `{ country: 'XX' }` when scoped, `{}` otherwise; spread into query params. */
  countryQuery: ComputedRef<{ country?: string }>
}

/**
 * Reads the `?country=XX` URL param, validates it against the alpha-2 regex and
 * normalizes it to upper case. The views own their own URL writes (their setters
 * push different query shapes), so this composable is read-only; it exposes the
 * validated value plus the ready-to-spread `countryQuery` both views need.
 */
export function useCountryFilter(): CountryFilter {
  const route = useRoute()

  const country = computed(() => {
    const c = route.query.country
    return typeof c === 'string' && ALPHA2.test(c) ? c.toUpperCase() : ''
  })
  const countryQuery = computed(() => (country.value ? { country: country.value } : {}))

  return { country, countryQuery }
}
