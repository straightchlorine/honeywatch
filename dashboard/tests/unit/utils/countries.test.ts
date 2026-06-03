import { describe, expect, it } from 'vitest'

import type { AsnResponse, CountryRowResponse } from '@/api/generated/types.gen'
import {
  buildAsnRows,
  buildCountryLeaderboardRows,
  countryCodeOf,
  countryDisplayName,
  COUNTRY_SORTS,
} from '@/utils/countries'

function country(over: Partial<CountryRowResponse>): CountryRowResponse {
  return {
    country_code: 'US',
    country: 'United States',
    sessions: 0,
    distinct_ips: 0,
    attempts: 0,
    successful: 0,
    success_rate: null,
    distinct_usernames: 0,
    distinct_passwords: 0,
    ...over,
  }
}

describe('COUNTRY_SORTS', () => {
  it('exposes the three UI sort axes', () => {
    expect(COUNTRY_SORTS.map((s) => s.id)).toEqual(['sessions', 'ips', 'success_rate'])
  })
})

describe('buildCountryLeaderboardRows', () => {
  const rows: CountryRowResponse[] = [
    country({ country_code: 'CN', country: 'China', sessions: 1200, distinct_ips: 50, success_rate: 1.2 }),
    country({ country_code: 'US', country: 'United States', sessions: 400, distinct_ips: 200, success_rate: 8.5 }),
  ]

  it('ranks the bar by the chosen sort metric, scaled to the max', () => {
    const bySessions = buildCountryLeaderboardRows(rows, 'sessions')
    // CN has the most sessions -> full-width bar; US is 400/1200.
    expect(bySessions[0]!.widthPct).toBe('100%')
    expect(bySessions[1]!.widthPct).toBe('33%')
    expect(bySessions[0]!.valueLabel).toBe('1,200')

    const byIps = buildCountryLeaderboardRows(rows, 'ips')
    // US has the most distinct IPs (200 vs 50): its bar is full width here.
    expect(byIps[1]!.widthPct).toBe('100%')
    expect(byIps[1]!.valueLabel).toBe('200')
  })

  it('formats the success-rate axis as a percentage (dash when null)', () => {
    const out = buildCountryLeaderboardRows(
      [country({ country_code: 'US', success_rate: 8.5 }), country({ country_code: 'RU', success_rate: null })],
      'success_rate',
    )
    expect(out[0]!.valueLabel).toBe('8.50%')
    expect(out[1]!.valueLabel).toBe('—')
  })

  it('marks a real country selectable with an upper-cased code and full name', () => {
    const [row] = buildCountryLeaderboardRows([country({ country_code: 'cn', country: null })], 'sessions')
    expect(row!.code).toBe('CN')
    expect(row!.selectable).toBe(true)
    // Name comes from the code even when the API name is null.
    expect(row!.label).toBe('China')
  })

  it('makes the geo-less Unknown bucket selectable via the ?? sentinel', () => {
    for (const code of ['??', null]) {
      const [row] = buildCountryLeaderboardRows(
        [country({ country_code: code, country: null })],
        'sessions',
      )
      expect(row!.selectable).toBe(true)
      expect(row!.code).toBe('??')
      expect(row!.label).toBe('Unknown')
    }
  })
})

describe('countryDisplayName', () => {
  it('resolves a full English name from the alpha-2 code', () => {
    expect(countryDisplayName('US')).toBe('United States')
    expect(countryDisplayName('cn')).toBe('China')
    expect(countryDisplayName('ID')).toBe('Indonesia')
  })

  it('reads the geo-less bucket and missing codes as Unknown', () => {
    expect(countryDisplayName('??')).toBe('Unknown')
    expect(countryDisplayName(null)).toBe('Unknown')
    expect(countryDisplayName(null, 'Unknown')).toBe('Unknown')
  })

  it('prefers the resolved name over a stale API name', () => {
    // API name may be null in prod; the code still yields the real name.
    expect(countryDisplayName('US', null)).toBe('United States')
  })
})

describe('countryCodeOf', () => {
  it('maps the bucket sentinel and null to ??, real codes to upper-case', () => {
    expect(countryCodeOf({ country_code: '??' })).toBe('??')
    expect(countryCodeOf({ country_code: null })).toBe('??')
    expect(countryCodeOf({ country_code: 'cn' })).toBe('CN')
  })
})

describe('buildAsnRows', () => {
  function asn(over: Partial<AsnResponse>): AsnResponse {
    return { asn: 16276, as_org: 'OVH SAS', sessions: 0, distinct_ips: 0, ...over }
  }

  it('labels by org, falling back to AS<number> then a generic name', () => {
    const out = buildAsnRows([
      asn({ as_org: 'OVH SAS', sessions: 10 }),
      asn({ as_org: null, asn: 4837, sessions: 5 }),
      asn({ as_org: null, asn: null, sessions: 1 }),
    ])
    expect(out[0]!.label).toBe('OVH SAS')
    expect(out[1]!.label).toBe('AS4837')
    expect(out[2]!.label).toBe('Unknown network')
  })

  it('scales bars to the busiest network and pluralizes IPs in the title', () => {
    const out = buildAsnRows([
      asn({ sessions: 10, distinct_ips: 3 }),
      asn({ sessions: 5, distinct_ips: 1 }),
    ])
    expect(out[0]!.widthPct).toBe('100%')
    expect(out[0]!.title).toContain('3 IPs')
    expect(out[1]!.widthPct).toBe('50%')
    expect(out[1]!.title).toContain('1 IP')
  })
})
