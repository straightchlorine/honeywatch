import { describe, expect, it } from 'vitest'
import type { SessionSummaryResponse } from '@/api/generated/types.gen'
import SessionListRow from '@/components/sessions/SessionListRow.vue'
import { mountWithProviders } from '../../../helpers/mount'

const base: SessionSummaryResponse = {
  id: 'abcdef0123456789',
  src_port: 51234,
  dst_port: 22,
  protocol: 'ssh',
  country_code: 'US',
  country: 'United States',
  city: 'Phoenix',
  lat: null,
  lon: null,
  started_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
  ended_at: new Date(Date.now() - 3 * 86_400_000 + 125_000).toISOString(),
  auth_attempt_count: 1,
  command_count: 2,
  has_successful_login: true,
  category: 'active',
  n_commands: 2,
  n_downloads: 1,
  n_tcpip: 0,
  auth_success: true,
  interest: 50,
  asn_org: null,
  client_version: 'SSH-2.0-Go',
}

const routes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/sessions/:id', name: 'session-detail', component: { template: '<div />' } },
]
const mountRow = (props: Partial<InstanceType<typeof SessionListRow>['$props']> = {}) =>
  mountWithProviders(SessionListRow, { props: { row: base, maxInterest: 100, ...props } }, routes)

describe('SessionListRow', () => {
  it('is a link to the session showing the first 8 characters of its id', () => {
    const w = mountRow()
    expect(w.element.tagName).toBe('A')
    expect(w.attributes('href')).toBe('/sessions/abcdef0123456789')
    expect(w.get('.id').text()).toBe('abcdef01')
    expect(w.attributes('title')).toMatch(/UTC$/)
  })

  it('names the row with the id, place, outcome and score', () => {
    expect(mountRow().attributes('aria-label')).toBe(
      'abcdef01, Phoenix, United States, got control and ran commands, interest 50 of 100',
    )
  })

  it('shows only the value the sort calls for', () => {
    expect(mountRow().find('.val').exists()).toBe(false)
    expect(mountRow({ sort: 'recent' }).get('.val').text()).toBe('3d ago')
    expect(mountRow({ sort: 'duration' }).get('.val').text()).toBe('2m 5s')
    expect(mountRow({ sort: 'country' }).find('.val').exists()).toBe(false)
  })

  it('names the country, not the city, when sorted by origin', () => {
    expect(mountRow().get('.place').text()).toBe('Phoenix')
    expect(mountRow({ sort: 'country' }).get('.place').text()).toBe('United States')
    const sg = mountRow({ row: { ...base, country: 'Singapore', city: 'Singapore' } })
    expect(sg.get('.place').text()).toBe('Singapore')
    expect(sg.attributes('aria-label')).toContain(', Singapore, got control')
  })

  it('gives each chip its words as an accessible name and prints none beside an outcome icon', () => {
    const chips = mountRow().findAll('.chip')
    expect(chips.map((c) => c.attributes('aria-label'))).toEqual([
      '2 commands typed',
      '1 file downloaded',
    ])
    expect(chips.every((c) => c.attributes('role') === 'img' && c.attributes('title'))).toBe(true)

    const quiet = mountRow({ row: { ...base, n_commands: 0, n_downloads: 0, category: 'login' } })
    expect(quiet.get('.chip').attributes('aria-label')).toBe('Got control, ran nothing')
    expect(quiet.get('.chip').classes()).toContain('only')
    // The words stay in the DOM for the name; .only hides them.
    expect(quiet.get('.chip.only .word').text()).toBe('control')
  })

  it('falls back to the outcome icon: probe is an eye, failed a login arrow, login a key', () => {
    const empty = { ...base, n_commands: 0, n_downloads: 0, n_tcpip: 0 }
    const chip = (category: SessionSummaryResponse['category']) =>
      mountRow({ row: { ...empty, category } }).get('.chip')
    expect(chip('probe').classes()).toContain('dim')
    expect(chip('probe').attributes('aria-label')).toBe('Connected, never tried to log in')
    expect(chip('failed').classes()).toContain('bad')
    expect(chip('login').classes()).toContain('ok')
  })

  it('hides the score hex from assistive tech, and a child has none', () => {
    const w = mountRow()
    expect(w.get('.lead').attributes('aria-hidden')).toBe('true')
    expect(w.find('.score-hex').exists()).toBe(true)
    expect(mountRow({ child: true }).find('.score-hex').exists()).toBe(false)
  })

  it('emits open when tapped', async () => {
    const w = mountRow()
    await w.trigger('click')
    expect(w.emitted('open')).toHaveLength(1)
  })
})
