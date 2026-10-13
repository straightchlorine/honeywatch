import { mount } from '@vue/test-utils'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

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

describe('SessionRow started stamp', () => {
  const startedCell = (started_at: string | null) =>
    mount(SessionRow, {
      props: { row: { ...baseRow, started_at }, expanded: false, maxInterest: 56 },
      global: { stubs: { SessionExpansion: true } },
    }).get('td.started')

  it('puts the UTC stamp to the second in the tooltip', () => {
    expect(startedCell('2026-05-28T12:34:00Z').attributes('title')).toBe('2026-05-28 12:34:00 UTC')
  })

  it('renders without a tooltip, not a RangeError, for an unparseable timestamp', () => {
    expect(startedCell('garbage').attributes('title')).toBeUndefined()
    expect(startedCell(null).attributes('title')).toBeUndefined()
  })
})

describe('SessionRow roving tabindex', () => {
  // jsdom has no clipboard, and the copy button only renders when it exists.
  beforeAll(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn() },
      configurable: true,
    })
  })
  afterAll(() => {
    Reflect.deleteProperty(navigator, 'clipboard')
  })

  const mountRow = (props: Record<string, unknown> = {}) =>
    mount(SessionRow, {
      props: { row: baseRow, expanded: false, maxInterest: 56, ...props },
      global: { stubs: { SessionExpansion: true } },
    })

  it('is tabbable only when it is the grid tab stop, copy button included', () => {
    const on = mountRow()
    const off = mountRow({ tabbable: false })
    expect(on.get('tr.srow').attributes('tabindex')).toBe('0')
    expect(on.get('.sid-copy').attributes('tabindex')).toBe('0')
    expect(off.get('tr.srow').attributes('tabindex')).toBe('-1')
    expect(off.get('.sid-copy').attributes('tabindex')).toBe('-1')
  })

  it.each([
    ['ArrowRight', false, 1],
    ['ArrowLeft', false, 0],
    ['ArrowRight', true, 0],
    ['ArrowLeft', true, 1],
  ])('%s with expanded=%s emits toggle %i time(s)', async (key, expanded, count) => {
    const w = mountRow({ expanded })
    await w.get('tr.srow').trigger('keydown', { key })
    expect(w.emitted('toggle') ?? []).toHaveLength(count)
  })

  it('ignores keys that bubble up from the copy button', async () => {
    const w = mountRow()
    await w.get('.sid-copy').trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('toggle')).toBeUndefined()
  })

  it('hides the empty spacer cell from assistive tech along with its header', () => {
    expect(mountRow().get('td.spacer').attributes('aria-hidden')).toBe('true')
  })
})

describe('SessionRow nested in an open run', () => {
  it('drops the hex and marks the row as a level-2 child', () => {
    const w = mount(SessionRow, {
      props: { row: baseRow, expanded: false, maxInterest: 56, nested: true },
    })
    expect(w.find('.score-hex').exists()).toBe(false)
    expect(w.find('tr.srow').classes()).toContain('nested')
    expect(w.find('tr.srow').attributes('aria-level')).toBe('2')
  })

  it('keeps its own story chips so the child reads on its own', () => {
    const w = mount(SessionRow, {
      props: { row: baseRow, expanded: false, maxInterest: 56, nested: true },
    })
    expect(w.findAll('.chips .chip')).toHaveLength(1)
  })

  it('keeps the hex on top-level rows', () => {
    const w = mount(SessionRow, { props: { row: baseRow, expanded: false, maxInterest: 56 } })
    expect(w.find('.score-hex').exists()).toBe(true)
    expect(w.find('tr.srow').attributes('aria-level')).toBeUndefined()
  })
})

describe('SessionRow chips', () => {
  it('gives wordless outcome chips an icon and a spoken name', () => {
    const w = mount(SessionRow, {
      props: {
        row: { ...baseRow, n_commands: 0, auth_success: false },
        expanded: false,
        maxInterest: 56,
      },
    })
    const chip = w.get('.chips .chip')
    expect(chip.attributes('role')).toBe('img')
    expect(chip.attributes('aria-label')).toBe('Logged in but never got a command prompt')
    expect(chip.find('svg.glyph').exists()).toBe(true)
  })
})
