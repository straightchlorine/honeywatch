import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import SessionExpansion from '@/components/sessions/SessionExpansion.vue'
import type { SessionDetailResponse } from '@/api/generated/types.gen'
import { mountWithProviders } from '../../../helpers/mount'

// Component builds all fields from one detail query; mock shapes the session per test branch.
let detail: SessionDetailResponse

vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  getSessionByIdOptions: ({ path }: { path: { session_id: string } }) => ({
    queryKey: ['session', path.session_id, detail],
    queryFn: async () => detail,
  }),
}))

function session(over: Partial<SessionDetailResponse> = {}): SessionDetailResponse {
  return {
    id: 'sess-1',
    src_port: 12345,
    dst_port: 22,
    protocol: 'ssh',
    sensor: 'edge-01',
    country: 'United States',
    country_code: 'US',
    city: null,
    lat: null,
    lon: null,
    started_at: '2026-05-31T13:40:00Z',
    ended_at: '2026-05-31T13:42:00Z',
    auth_attempts: [],
    commands: [],
    downloads: [],
    ...over,
  } as SessionDetailResponse
}

// RouterLink stub drops its slot with the badge; use real component and define named routes.
const ROUTES = [
  { path: '/', component: { template: '<div />' } },
  { path: '/payloads', name: 'payloads', component: { template: '<div />' } },
  { path: '/sessions/:id', name: 'session-detail', component: { template: '<div />' } },
]

async function mountWith(over: Partial<SessionDetailResponse> = {}) {
  detail = session(over)
  const w = mountWithProviders(SessionExpansion, { props: { sessionId: detail.id } }, ROUTES)
  await flushPromises()
  return w
}

describe('SessionExpansion', () => {
  it('announces loading to assistive tech before the query resolves', () => {
    detail = session()
    const w = mountWithProviders(SessionExpansion, { props: { sessionId: 'sess-1' } }, ROUTES)
    const loading = w.get('.loading')
    expect(loading.attributes('role')).toBe('status')
    expect(w.find('.facts').exists()).toBe(false)
  })

  it('renders one credential row per attempt, tagged accepted or rejected', async () => {
    const w = await mountWith({
      auth_attempts: [
        { id: 1, username: 'root', password: 'toor', success: false },
        { id: 2, username: 'admin', password: 'admin', success: true },
      ] as SessionDetailResponse['auth_attempts'],
    })
    const rows = w.findAll('.facts .cred')
    expect(rows.map((r) => r.text())).toEqual([
      'root:toor (rejected)',
      'admin:admin (accepted)',
    ])
    expect(rows[0]?.classes()).toContain('cred-no')
    expect(rows[1]?.classes()).toContain('cred-ok')
  })

  it('never renders a raw IP address found in a password', async () => {
    const w = await mountWith({
      auth_attempts: [
        { id: 1, username: 'root', password: 'login 203.0.113.7 now', success: false },
      ] as SessionDetailResponse['auth_attempts'],
    })
    const text = w.get('.facts .cred').text()
    expect(text).not.toContain('203.0.113.7')
    expect(w.html()).not.toContain('203.0.113.7')
  })

  it('marks a blank username or password as empty rather than rendering a bare colon', async () => {
    const w = await mountWith({
      auth_attempts: [
        { id: 1, username: '', password: '', success: false },
      ] as SessionDetailResponse['auth_attempts'],
    })
    expect(w.get('.facts .cred').text()).toContain('(blank):(blank)')
  })

  it('shows the payload badge with the first 16 sha256 chars only when a download exists', async () => {
    const sha = 'a'.repeat(40) + 'b'.repeat(24)
    const withDl = await mountWith({
      downloads: [{ id: 1, url: null, sha256: sha, timestamp: null }] as SessionDetailResponse['downloads'],
    })
    expect(withDl.text()).toContain(sha.slice(0, 16))
    expect(withDl.text()).not.toContain(sha)

    const without = await mountWith({ downloads: [] as SessionDetailResponse['downloads'] })
    expect(without.text()).not.toContain('Payload')
  })

  it('builds the client line from the protocol, uppercased', async () => {
    const w = await mountWith({ protocol: 'ssh' })
    expect(w.text()).toContain('SSH-2.0-SSH')
  })

  it('renders the transcript through TerminalLine, framed by banner and close', async () => {
    const w = await mountWith({ commands: [] as SessionDetailResponse['commands'] })
    const term = w.get('.term')
    expect(term.text()).toContain('Connecting to')
    expect(w.find('.empty').exists()).toBe(false)
  })

  it('exposes the transcript as a keyboard-reachable log region', async () => {
    const w = await mountWith()
    const term = w.get('.term')
    expect(term.attributes('role')).toBe('log')
    expect(term.attributes('tabindex')).toBe('0')
    expect(term.attributes('aria-label')).toBe('Command transcript preview')
  })
})
