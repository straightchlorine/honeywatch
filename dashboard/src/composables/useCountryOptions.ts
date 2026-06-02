/**
 * Country dropdown options reused by ActivityView and SessionsView. Both build
 * the same list from the top-countries leaderboard (max 100); only the leading
 * all-countries label differs ('the world' vs 'All countries'), so that is the
 * one parameter. Not awaited by callers: the views render before this resolves.
 */
import { computed, type ComputedRef } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { statsTopCountriesOptions } from '@/api/queries'
import { isAlpha2 } from './useCountryFilter'

export interface Opt {
  value: string
  label: string
}

/**
 * Wraps the top-countries query + `{ value, label }` mapping. The default option
 * (`value: ''`) scopes to every country and reads as `allLabel`; the rest are the
 * leaderboard entries with a valid alpha-2 code, labelled by country name (code
 * as fallback).
 */
export function useCountryOptions(allLabel: string): ComputedRef<Opt[]> {
  const countriesQ = useQuery({ ...statsTopCountriesOptions({ query: { top_n: 100 } }) })

  return computed<Opt[]>(() => [
    { value: '', label: allLabel },
    ...(countriesQ.data.value ?? [])
      .filter((c) => isAlpha2(c.country_code))
      .map((c) => ({
        value: c.country_code as string,
        label: (c.country ?? c.country_code) as string,
      })),
  ])
}
