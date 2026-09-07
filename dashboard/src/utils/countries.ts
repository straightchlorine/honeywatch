import type { AsnResponse, CountryRowResponse, StatsCountriesData } from '@/api/generated/types.gen'
import { isAlpha2 } from '@/composables/useCountryFilter'
import { fmtNumber } from './format'
import { fmtSuccessRate, pctWidth } from './credentials'
import type { RankRow } from '@/components/base/RankList.vue'

/** Sort order the API accepts; derived from generated client to stay in sync. `attempts` is valid but intentionally not exposed in the UI. */
export type CountrySort = NonNullable<NonNullable<StatsCountriesData['query']>['sort']>

export const COUNTRY_SORTS: { id: CountrySort; label: string }[] = [
  { id: 'sessions', label: 'Sessions' },
  { id: 'ips', label: 'Unique IPs' },
  { id: 'success_rate', label: 'Success rate' },
]

/** Sentinel code for the geo-less bucket (mirrors the API's COALESCE '??'). */
export const UNKNOWN_CODE = '??'

/** World country count: 193 UN member states + 2 UN observer states (Vatican City, Palestine). */
export const WORLD_COUNTRY_COUNT = 195

// Intl.DisplayNames as fallback: geoip enrichment leaves country names null when
// an IP is in the ASN DB but not the City DB, making API names unreliable.
const REGION = new Intl.DisplayNames(['en'], { type: 'region' })

export function countryDisplayName(code: string | null, apiName?: string | null): string {
  if (!code || code === UNKNOWN_CODE) return apiName ?? 'Unknown'
  if (isAlpha2(code)) {
    try {
      return REGION.of(code.toUpperCase()) ?? apiName ?? code
    } catch {
      return apiName ?? code
    }
  }
  return apiName ?? code
}

/** Selection code: '??' for Unknown, upper-cased alpha-2 for countries, '' if unselectable. */
export function countryCodeOf(row: { country_code: string | null }): string {
  if (row.country_code === UNKNOWN_CODE || row.country_code === null) return UNKNOWN_CODE
  return isAlpha2(row.country_code) ? row.country_code.toUpperCase() : ''
}

/** Null success_rate values read as 0. */
function metricValue(row: CountryRowResponse, sort: CountrySort): number {
  if (sort === 'ips') return row.distinct_ips
  if (sort === 'success_rate') return row.success_rate ?? 0
  return row.sessions
}

interface CountryLeaderRow {
  key: string
  code: string
  label: string
  valueLabel: string
  widthPct: string
  title: string
  /** Only countries and Unknown bucket are clickable; '' codes are not. */
  selectable: boolean
}

/** Bars scale to the max value in the current result set. */
export function buildCountryLeaderboardRows(
  rows: CountryRowResponse[],
  sort: CountrySort,
): CountryLeaderRow[] {
  let max = 0
  for (const r of rows) {
    const v = metricValue(r, sort)
    if (v > max) max = v
  }
  return rows.map((r, idx) => {
    const code = countryCodeOf(r)
    const label = countryDisplayName(r.country_code, r.country)
    const v = metricValue(r, sort)
    const valueLabel = sort === 'success_rate' ? fmtSuccessRate(r.success_rate) : fmtNumber(v)
    return {
      key: code || `unselectable-${idx}`,
      code,
      label,
      valueLabel,
      widthPct: pctWidth(v, max),
      title:
        `${label} - ${fmtNumber(r.sessions)} sessions, ${fmtNumber(r.distinct_ips)} IPs, ` +
        `${fmtSuccessRate(r.success_rate)} accepted`,
      selectable: code !== '',
    }
  })
}

export function buildAsnRows(items: AsnResponse[]): RankRow[] {
  let max = 0
  for (const it of items) if (it.sessions > max) max = it.sessions
  return items.map((it) => {
    const label = it.as_org ?? (it.asn !== null ? `AS${it.asn}` : 'Unknown network')
    const ips = it.distinct_ips
    return {
      label,
      value: fmtNumber(it.sessions),
      frac: it.sessions / max,
      title: [
        it.asn !== null ? `AS${it.asn}` : 'Unknown network',
        `${fmtNumber(it.sessions)} sessions`,
        `${fmtNumber(ips)} IP${ips === 1 ? '' : 's'}`,
      ]
        .filter(Boolean)
        .join(' - '),
    }
  })
}
