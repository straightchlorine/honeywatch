import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SessionRow from '@/components/sessions/SessionRow.vue'
import type { SessionSummaryResponse } from '@/api/generated/types.gen'

const baseRow: SessionSummaryResponse = {
  id: 'sess-0001aaaa',
  src_port: 51234,
  dst_port: 22,
  protocol: 'ssh',
  country_code: 'US',
  country: 'United States',
  city: null,
  lat: null,
  lon: null,
  started_at: '2026-05-28T12:34:00Z',
  ended_at: '2026-05-28T12:40:00Z',
  auth_attempt_count: 5,
  command_count: 3,
  has_successful_login: true,
  category: 'active',
  n_commands: 3,
  n_downloads: 0,
  n_tcpip: 0,
  auth_success: true,
  interest: 28,
  asn_org: 'OVH SAS',
  client_version: 'SSH-2.0-libssh2_1.10.0',
}

describe('SessionRow interest badge', () => {
  it('normalizes the displayed score to 0-100 relative to the maxInterest prop', () => {
    const w = mount(SessionRow, {
      props: { row: baseRow, expanded: false, maxInterest: 56 },
    })
    expect(w.find('.score-hex b').text()).toBe('50')
  })

  it('shows the current hottest session as exactly 100', () => {
    const w = mount(SessionRow, {
      props: { row: { ...baseRow, interest: 56 }, expanded: false, maxInterest: 56 },
    })
    expect(w.find('.score-hex b').text()).toBe('100')
  })

  it('keeps the raw interest score visible in the tooltip, de-emphasized on the badge', () => {
    const w = mount(SessionRow, {
      props: { row: baseRow, expanded: false, maxInterest: 56 },
    })
    const scoreHex = w.find('.score-hex')
    expect(scoreHex.exists()).toBe(true)
    expect(scoreHex.element.textContent).toContain('50') // normalized score
    expect(w.find('.score-hex b').text()).not.toBe('28')
  })

  it('never divides by zero when maxInterest is 0 (empty/unseeded dataset)', () => {
    const w = mount(SessionRow, {
      props: { row: { ...baseRow, interest: 0 }, expanded: false, maxInterest: 0 },
    })
    expect(w.find('.score-hex b').text()).toBe('0')
  })
})
