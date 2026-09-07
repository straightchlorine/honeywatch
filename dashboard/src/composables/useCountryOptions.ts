/**
 * Shared country options from the top-countries leaderboard, with customizable "all countries" label.
 */
import { computed, type ComputedRef } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { statsTopCountriesOptions } from '@/api/queries'
import { isAlpha2 } from './useCountryFilter'
import { useCountryFlag } from './useCountryFlag'

export interface Opt {
  value: string
  label: string
  icon?: string
}

/**
 * Filters to valid alpha-2 codes; some leaderboard entries lack them.
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
        icon: useCountryFlag(c.country_code as string),
      })),
  ])
}
