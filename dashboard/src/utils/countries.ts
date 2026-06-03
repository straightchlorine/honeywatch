import type { AsnResponse, CountryRowResponse } from '@/api/generated/types.gen'
import { isAlpha2 } from '@/composables/useCountryFilter'
import { fmtNumber } from './format'
import { fmtSuccessRate, pctWidth, type BarRow } from './credentials'

/**
 * Leaderboard sort axes exposed in the UI. Maps 1:1 onto the API's `sort`
 * query param (which also accepts `attempts`, unused here). `success_rate`
 * ranks by accept-rate; the others by their raw counts.
 */
export type CountrySort = 'sessions' | 'ips' | 'success_rate'

export const COUNTRY_SORTS: { id: CountrySort; label: string }[] = [
  { id: 'sessions', label: 'Sessions' },
  { id: 'ips', label: 'Unique IPs' },
  { id: 'success_rate', label: 'Success rate' },
]

/** Sentinel code for the geo-less bucket (mirrors the API's COALESCE '??'). */
export const UNKNOWN_CODE = '??'

// Resolve full English country names from the alpha-2 code via the built-in
// Intl table -- the geoip enrichment leaves `country` (name) null when an IP is
// in the ASN DB but not the City DB, so the API name alone is unreliable.
const REGION = new Intl.DisplayNames(['en'], { type: 'region' })

/**
 * Full country name for display: the geo-less bucket reads "Unknown"; a valid
 * alpha-2 resolves to its English name (falling back to the API name or the raw
 * code if Intl can't); anything else uses the API name or code.
 */
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

/**
 * Canonical selection code for a leaderboard row: '??' for the geo-less bucket,
 * the upper-cased alpha-2 for a real country, '' for anything unselectable.
 */
export function countryCodeOf(row: { country_code: string | null }): string {
  if (row.country_code === UNKNOWN_CODE || row.country_code === null) return UNKNOWN_CODE
  return isAlpha2(row.country_code) ? row.country_code.toUpperCase() : ''
}

/** Pull the metric a given sort ranks by (success_rate nulls read as 0). */
function metricValue(row: CountryRowResponse, sort: CountrySort): number {
  if (sort === 'ips') return row.distinct_ips
  if (sort === 'success_rate') return row.success_rate ?? 0
  return row.sessions
}

export interface CountryLeaderRow {
  key: string
  /** Alpha-2 code, '??' for the geo-less Unknown bucket, or '' if unselectable. */
  code: string
  label: string
  /** The sorted-metric value, formatted for the trailing column. */
  valueLabel: string
  widthPct: string
  title: string
  /** Real countries and the Unknown bucket drill down; '' codes do not. */
  selectable: boolean
}

/**
 * Build the master leaderboard rows. The bar reflects whichever metric `sort`
 * ranks by (so the longest bar is always the top row), scaled to the max in the
 * current list. The Unknown/`??` bucket stays visible but non-interactive.
 */
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
        `${label} — ${fmtNumber(r.sessions)} sessions, ${fmtNumber(r.distinct_ips)} IPs, ` +
        `${fmtSuccessRate(r.success_rate)} accepted`,
      selectable: code !== '',
    }
  })
}

/** Map the ASN/source-network breakdown onto display-ready bar rows. */
export function buildAsnRows(items: AsnResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.sessions > max) max = it.sessions
  return items.map((it, idx) => {
    const label = it.as_org ?? (it.asn !== null ? `AS${it.asn}` : 'Unknown network')
    const ips = it.distinct_ips
    return {
      key: `${it.asn ?? 'na'}-${idx}`,
      label,
      count: it.sessions,
      widthPct: pctWidth(it.sessions, max),
      title:
        `${label}${it.asn !== null ? ` (AS${it.asn})` : ''} — ` +
        `${fmtNumber(it.sessions)} sessions, ${fmtNumber(ips)} IP${ips === 1 ? '' : 's'}`,
    }
  })
}
