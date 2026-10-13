import { describe, expect, it } from 'vitest'
import type { SessionSummaryResponse } from '@/api/generated/types.gen'
import SessionsPhoneList from '@/components/sessions/SessionsPhoneList.vue'
import { mountWithProviders } from '../../../helpers/mount'

const session = (id: string): SessionSummaryResponse => ({
  id,
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
})
const run = {
  count: 1234,
  offset: 1,
  countries: 1,
  country_code: 'PE',
  country: 'Peru',
  min_duration_s: 4,
  max_duration_s: 58,
  oldest: '2026-01-01T00:00:00Z',
  newest: '2026-01-02T00:00:00Z',
}
const plain = session('plain000aaaa')
const lead = { ...session('lead0000bbbb'), run }
const kids = [session('kid00001cccc'), session('kid00002dddd')]

const routes = [
  { path: '/', component: { template: '<div />' } },
  { path: '/sessions/:id', name: 'session-detail', component: { template: '<div />' } },
]
function mountList(over: Record<string, unknown> = {}) {
  return mountWithProviders(
    SessionsPhoneList,
    {
      props: {
        rows: [plain, lead],
        members: new Map(),
        openRuns: new Map(),
        sort: 'interest',
        maxInterest: 20,
        busy: false,
        runLoading: () => false,
        moreLabel: () => 'Show 40 more of 1,232',
        ...over,
      },
    },
    routes,
  )
}

describe('SessionsPhoneList', () => {
  it('is a labelled list with one item per row and a link inside each', () => {
    const w = mountList()
    expect(w.get('ul').attributes('aria-label')).toBe('Sessions')
    expect(w.findAll('ul.sessions-phone > li')).toHaveLength(2)
    expect(w.findAll('a.row')).toHaveLength(2)
  })

  it('gives a run a head button with its count, closed by default', () => {
    const w = mountList()
    expect(w.findAll('.run-head')).toHaveLength(1)
    const head = w.get('.run-head')
    expect(head.get('.cnt').text()).toBe('1,234')
    expect(head.get('.lbl').text()).toBe('more like this')
    expect(head.attributes('aria-expanded')).toBe('false')
    expect(head.attributes('aria-controls')).toBe('kids-lead0000bbbb')
    expect(w.get('#kids-lead0000bbbb').attributes('style')).toContain('display: none')
  })

  it('lists the members under an open run, named for the session they match', () => {
    const w = mountList({
      openRuns: new Map([['lead0000bbbb', 1]]),
      members: new Map([['lead0000bbbb', kids]]),
    })
    expect(w.get('.run-head').attributes('aria-expanded')).toBe('true')
    const list = w.get('#kids-lead0000bbbb')
    expect(list.attributes('aria-label')).toBe('Sessions like lead0000')
    expect(list.findAll('a.row.child').map((a) => a.attributes('data-id'))).toEqual([
      'kid00001cccc',
      'kid00002dddd',
    ])
    expect(w.find('li.open').exists()).toBe(true)
  })

  it('asks the view to toggle a run, load more, and note the opened session', async () => {
    const w = mountList({
      openRuns: new Map([['lead0000bbbb', 1]]),
      members: new Map([['lead0000bbbb', kids]]),
    })
    await w.get('.run-head').trigger('click')
    expect(w.emitted('toggle-run')).toEqual([['lead0000bbbb']])
    const more = w.get('.more button')
    expect(more.text()).toBe('Show 40 more of 1,232')
    await more.trigger('click')
    expect(w.emitted('more')).toEqual([['lead0000bbbb']])
    await w.get('a.row.child').trigger('click')
    expect(w.emitted('open')).toEqual([['kid00001cccc']])
  })

  it('shows Loading while a run page is in flight, and no button once every member is in', () => {
    const open = new Map([['lead0000bbbb', 1]])
    const loading = mountList({
      openRuns: open,
      members: new Map([['lead0000bbbb', kids]]),
      runLoading: () => true,
    })
    expect(loading.get('.more [role="status"]').text()).toBe('Loading\u2026')
    expect(loading.find('.more button').exists()).toBe(false)

    // A small run: rendering all 1,234 members under jsdom exceeded the 5s timeout in CI.
    const small = { ...lead, run: { ...run, count: 8 } }
    const all = Array.from({ length: small.run.count }, (_, i) => session(`m${i}`))
    const done = mountList({
      rows: [plain, small],
      openRuns: open,
      members: new Map([['lead0000bbbb', all]]),
    })
    expect(done.find('.more').exists()).toBe(false)
  })

  it('marks the list busy while the previous page is held on screen', () => {
    expect(mountList({ busy: true }).get('ul').attributes('aria-busy')).toBe('true')
  })
})
