import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TerminalLine from '@/components/sessions/TerminalLine.vue'

describe('TerminalLine', () => {
  it('renders a command line with prompt and bright input', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c1',
          kind: 'command',
          user: 'admin',
          segments: [{ text: 'whoami', redacted: false }],
        },
      },
    })
    expect(w.find('.prompt').text()).toContain('admin@honeypot')
    expect(w.find('.input').text()).toContain('whoami')
  })

  it('wraps redacted segments in an ip-blot span', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c1',
          kind: 'command',
          user: 'admin',
          segments: [
            { text: 'wget ', redacted: false },
            { text: '‹ip›', redacted: true },
          ],
        },
      },
    })
    const blot = w.find('.ip-blot')
    expect(blot.exists()).toBe(true)
    expect(blot.text()).toContain('‹ip›')
    expect(blot.attributes('title')).toContain('IP')
    // Visually-hidden text makes the blot meaningful to screen readers (not via title).
    expect(blot.find('.visually-hidden').text()).toContain('IP address redacted')
  })

  it('marks non-command lines as annotations wrapped in guillemets', () => {
    const w = mount(TerminalLine, {
      props: { line: { id: 'b', kind: 'banner', text: 'Connecting…' } },
    })
    expect(w.find('.annotation').text()).toContain('‹')
    expect(w.find('.annotation').text()).toContain('Connecting')
    expect(w.find('.prompt').exists()).toBe(false)
  })
})
