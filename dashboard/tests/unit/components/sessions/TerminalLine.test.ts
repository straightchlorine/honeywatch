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

  it('shows the supplied password as a highlighted credential chip', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a1',
          kind: 'auth-fail',
          pre: "root@honeypot's password: ",
          password: 'hunter2',
          post: ' — Permission denied (password).',
        },
      },
    })
    const cred = w.find('.cred')
    expect(cred.exists()).toBe(true)
    expect(cred.text()).toBe('hunter2')
    const text = w.find('.annotation').text()
    expect(text).toContain("root@honeypot's password:")
    expect(text).toContain('Permission denied')
  })

  it('marks an auth line with no supplied password explicitly', () => {
    const w = mount(TerminalLine, {
      props: {
        line: { id: 'a2', kind: 'auth-ok', pre: 'Accepted password ', password: '', post: ' for root.' },
      },
    })
    const cred = w.find('.cred')
    expect(cred.classes()).toContain('cred-empty')
    expect(cred.find('.visually-hidden').text()).toContain('no password')
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
