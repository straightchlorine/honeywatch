import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TerminalLine from '@/components/sessions/TerminalLine.vue'
import type { TerminalLine as TerminalLineType } from '@/components/sessions/useTerminalTranscript'

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

  it('renders the capture time in the left gutter', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c1',
          kind: 'command',
          user: 'root',
          segments: [{ text: 'ls', redacted: false }],
          time: '13:41:49',
        },
      },
    })
    expect(w.find('.ts').text()).toBe('13:41:49')
  })

  it('renders with no timestamp when time is undefined', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c1',
          kind: 'command',
          user: 'root',
          segments: [{ text: 'ls', redacted: false }],
        },
      },
    })
    expect(w.find('.ts').text()).toBe('')
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
            { text: '<ip>', redacted: true },
          ],
        },
      },
    })
    const blot = w.find('.ip-blot')
    expect(blot.exists()).toBe(true)
    expect(blot.text()).toContain('<ip>')
    // Visually-hidden text makes the blot meaningful to screen readers.
    expect(blot.find('.visually-hidden').text()).toContain('IP address hidden')
  })

  it('handles multiple mixed redacted and non-redacted segments', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c2',
          kind: 'command',
          user: 'admin',
          segments: [
            { text: 'curl http://', redacted: false },
            { text: '<ip>', redacted: true },
            { text: ':8080/data', redacted: false },
          ],
        },
      },
    })
    const input = w.find('.input')
    expect(input.text()).toContain('curl http://')
    expect(input.text()).toContain(':8080/data')
    expect(w.findAll('.ip-blot')).toHaveLength(1)
  })

  it('renders IP blots with proper accessibility attributes for tooltips', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c3',
          kind: 'command',
          user: 'root',
          segments: [
            { text: 'ping ', redacted: false },
            { text: '<ip>', redacted: true },
          ],
        },
      },
    })
    const blot = w.find('.ip-blot')
    expect(blot.attributes('tabindex')).toBe('0')
    expect(blot.element).toBeDefined()
  })

  it('shows the supplied password as a highlighted credential chip', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a1',
          kind: 'auth-fail',
          pre: "root@honeypot's password: ",
          password: 'hunter2',
          post: ' - Permission denied (password).',
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

  it('displays password with special characters without escaping in the chip', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a2',
          kind: 'auth-fail',
          pre: 'password: ',
          password: 'p@ss!w0rd#2024',
          post: ' failed.',
        },
      },
    })
    const cred = w.find('.cred')
    expect(cred.text()).toBe('p@ss!w0rd#2024')
  })

  it('marks an auth line with no supplied password explicitly', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a3',
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password: '',
          post: ' for root.',
        },
      },
    })
    const cred = w.find('.cred')
    expect(cred.classes()).toContain('cred-empty')
    expect(cred.text()).toContain('(blank)')
    expect(cred.find('.visually-hidden').text()).toContain('no password')
  })

  it('renders auth-ok lines with the correct annotation structure', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a4',
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password: 'secret',
          post: ' for user.',
          time: '14:30:00',
        },
      },
    })
    const annotation = w.find('.annotation')
    expect(annotation.exists()).toBe(true)
    expect(annotation.text()).toContain('Accepted password')
    expect(annotation.text()).toContain('secret')
    expect(annotation.text()).toContain('for user.')
  })

  it('renders auth-fail lines with proper CSS class', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a5',
          kind: 'auth-fail',
          pre: "user@honeypot's password: ",
          password: 'wrongpass',
          post: ' - Permission denied.',
        },
      },
    })
    const line = w.find('.line')
    expect(line.classes()).toContain('line-auth-fail')
  })

  it('renders auth-ok lines with proper CSS class', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a6',
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password: 'pass',
          post: ' for user.',
        },
      },
    })
    const line = w.find('.line')
    expect(line.classes()).toContain('line-auth-ok')
  })

  it('marks non-command lines as annotations wrapped in angle brackets', () => {
    const w = mount(TerminalLine, {
      props: { line: { id: 'b', kind: 'banner', text: 'Connecting...' } },
    })
    expect(w.find('.annotation').text()).toContain('<')
    expect(w.find('.annotation').text()).toContain('Connecting')
    expect(w.find('.annotation').text()).toContain('>')
    expect(w.find('.prompt').exists()).toBe(false)
  })

  it('renders download lines as annotations', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'dl1',
          kind: 'download',
          text: 'downloaded file: <ip>/malware.bin',
          time: '13:42:00',
        },
      },
    })
    expect(w.find('.annotation').exists()).toBe(true)
    expect(w.find('.annotation').text()).toContain('downloaded file')
    expect(w.find('.line').classes()).toContain('line-download')
  })

  it('renders closed lines as annotations', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'closed1',
          kind: 'closed',
          text: 'Connection to honeypot closed. Session lasted 5m 30s.',
          time: '13:50:00',
        },
      },
    })
    expect(w.find('.annotation').exists()).toBe(true)
    expect(w.find('.annotation').text()).toContain('Connection')
    expect(w.find('.annotation').text()).toContain('closed')
    expect(w.find('.line').classes()).toContain('line-closed')
  })

  it('ensures HTML angle brackets in annotations use aria-hidden for semantic brackets', () => {
    const w = mount(TerminalLine, {
      props: {
        line: { id: 'b2', kind: 'banner', text: 'Connected' },
      },
    })
    const annotation = w.find('.annotation')
    const ariaHidden = annotation.findAll('[aria-hidden="true"]')
    expect(ariaHidden.length).toBeGreaterThan(0)
  })

  it('preserves angle brackets in annotation text content', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'b3',
          kind: 'banner',
          text: 'SSH banner: OpenSSH 7.4',
        },
      },
    })
    const annotation = w.find('.annotation')
    const text = annotation.element.textContent
    expect(text).toContain('<')
    expect(text).toContain('SSH banner')
    expect(text).toContain('>')
  })

  it('password credential chip has proper tabindex for accessibility', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a7',
          kind: 'auth-fail',
          pre: 'password: ',
          password: 'testpass',
          post: ' failed.',
        },
      },
    })
    const cred = w.find('.cred:not(.cred-empty)')
    expect(cred.attributes('tabindex')).toBe('0')
  })

  it('empty password credential is rendered without tabindex', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a8',
          kind: 'auth-ok',
          pre: 'Accepted password ',
          password: '',
          post: ' for user.',
        },
      },
    })
    const cred = w.find('.cred-empty')
    expect(cred.exists()).toBe(true)
    expect(cred.element.textContent).toContain('blank')
  })

  it('renders command line with long input text', () => {
    const longCmd = 'echo ' + 'x'.repeat(200)
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c4',
          kind: 'command',
          user: 'admin',
          segments: [{ text: longCmd, redacted: false }],
        },
      },
    })
    expect(w.find('.input').text()).toContain('echo')
    expect(w.find('.input').text()).toContain('x'.repeat(50))
  })

  it('handles command with only redacted segments', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c5',
          kind: 'command',
          user: 'root',
          segments: [{ text: '<ip>', redacted: true }],
        },
      },
    })
    expect(w.findAll('.ip-blot')).toHaveLength(1)
    expect(w.find('.input').text()).toContain('<ip>')
  })

  it('handles multiple consecutive redacted segments', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'c6',
          kind: 'command',
          user: 'admin',
          segments: [
            { text: '<ip>', redacted: true },
            { text: ' ', redacted: false },
            { text: '<ip>', redacted: true },
          ],
        },
      },
    })
    const blots = w.findAll('.ip-blot')
    expect(blots).toHaveLength(2)
    expect(blots.map((b) => b.text())).toEqual([
      '<ip> (IP address hidden)',
      '<ip> (IP address hidden)',
    ])
    const inputText = w.find('.input').element.textContent
    expect(inputText).toContain('<ip>')
  })

  it('does not render command prompt for non-command lines', () => {
    const w = mount(TerminalLine, {
      props: {
        line: {
          id: 'a9',
          kind: 'auth-ok',
          pre: 'Accepted ',
          password: 'pass',
          post: ' for user.',
        },
      },
    })
    expect(w.find('.prompt').exists()).toBe(false)
    expect(w.find('.input').exists()).toBe(false)
  })

  it('line wrapper has correct CSS class for line kind', () => {
    const kinds: Array<[string, string]> = [
      ['command', 'line-command'],
      ['banner', 'line-banner'],
      ['download', 'line-download'],
      ['closed', 'line-closed'],
    ]
    for (const [kind, expectedClass] of kinds) {
      let lineData: TerminalLineType
      if (kind === 'command') {
        lineData = {
          id: `test-${kind}`,
          kind: 'command',
          user: 'root',
          segments: [{ text: 'cmd', redacted: false }],
        }
      } else if (kind === 'banner') {
        lineData = {
          id: `test-${kind}`,
          kind: 'banner',
          text: 'test text',
        }
      } else if (kind === 'download') {
        lineData = {
          id: `test-${kind}`,
          kind: 'download',
          text: 'test text',
        }
      } else {
        lineData = {
          id: `test-${kind}`,
          kind: 'closed',
          text: 'test text',
        }
      }
      const w = mount(TerminalLine, { props: { line: lineData } })
      expect(w.find('.line').classes()).toContain(expectedClass)
    }
  })
})
