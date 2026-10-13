import { mount } from '@vue/test-utils'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import SessionGroupRow from '@/components/sessions/SessionGroupRow.vue'
import type { RunSummaryResponse, SessionSummaryResponse } from '@/api/generated/types.gen'

const row: SessionSummaryResponse = {
  id: 'sess-0001aaaa',
  src_port: 51234,
  dst_port: 22,
  protocol: 'ssh',
  country_code: 'PE',
  country: 'Peru',
  city: null,
  lat: null,
  lon: null,
  started_at: '2026-01-02T00:00:00Z',
  ended_at: '2026-01-02T00:00:30Z',
  auth_attempt_count: 1,
  command_count: 2,
  has_successful_login: true,
  category: 'active',
  n_commands: 2,
  n_downloads: 0,
  n_tcpip: 0,
  auth_success: true,
  interest: 7,
  asn_org: null,
  client_version: 'SSH-2.0-Go',
}
const run: RunSummaryResponse = {
  count: 12,
  offset: 1,
  countries: 3,
  country_code: null,
  country: null,
  min_duration_s: 4,
  max_duration_s: 58,
  oldest: '2026-01-01T00:00:00Z',
  newest: '2026-01-02T00:00:00Z',
}

const cells = (r: RunSummaryResponse) =>
  mount(SessionGroupRow, {
    attachTo: document.createElement('tbody'),
    props: { row, run: r, open: false },
  })
    .findAll('td')
    .map((td) => td.text())

describe('SessionGroupRow', () => {
  beforeAll(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-03T00:00:00Z'))
  })
  afterAll(() => vi.useRealTimers())

  it('summarises the folded sessions from the run, not from loaded rows', () => {
    const [label, story, origin, , duration, started] = cells(run)
    expect(label).toContain('12')
    expect(label).toContain('more like this')
    expect(story).toContain('2')
    expect(origin).toBe('3 countries')
    expect(duration).toBe('4-58s')
    expect(started).toMatch(/ to /)
  })

  it('groups the run count in thousands', () => {
    expect(cells({ ...run, count: 1236 })[0]).toContain('1,236')
  })

  it('names the one country, ranges minutes, and dashes what is unknown', () => {
    const one = { ...run, countries: 1, country_code: 'PE', country: 'Peru' }
    expect(cells(one)[2]).toContain('Peru')
    expect(cells({ ...run, min_duration_s: 90, max_duration_s: 600 })[4]).toBe('2m-10m')
    expect(cells({ ...run, min_duration_s: null, max_duration_s: null })[4]).toBe('-')
    // both ends round to the same minute: one value, not "1m-1m"
    expect(cells({ ...run, min_duration_s: 61, max_duration_s: 89 })[4]).toBe('1m')
    expect(cells({ ...run, countries: 0 })[2]).toBe('-')
  })

  it('toggles on Enter and on click', async () => {
    const w = mount(SessionGroupRow, {
      attachTo: document.createElement('tbody'),
      props: { row, run, open: false },
    })
    await w.get('tr').trigger('keydown', { key: 'Enter' })
    await w.get('tr').trigger('click')
    expect(w.emitted('toggle')).toHaveLength(2)
  })
})
