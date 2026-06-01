import { describe, expect, it } from 'vitest'

import { classifySession } from '@/utils/sessionClass'

describe('classifySession', () => {
  it('marks sessions with commands as CLI (shell activity wins)', () => {
    const c = classifySession({ command_count: 3, login_success: true, auth_attempt_count: 5 })
    expect(c.kind).toBe('active')
    expect(c.label).toBe('CLI')
    expect(c.title).toContain('3 commands')
  })

  it('singularizes a single command', () => {
    const c = classifySession({ command_count: 1, login_success: false, auth_attempt_count: 1 })
    expect(c.title).toBe('1 command run')
  })

  it('marks a bare successful login (no commands) as Login', () => {
    const c = classifySession({ command_count: 0, login_success: true, auth_attempt_count: 2 })
    expect(c.kind).toBe('login')
  })

  it('marks attempts-without-success as Failed auth', () => {
    const c = classifySession({ command_count: 0, login_success: false, auth_attempt_count: 4 })
    expect(c.kind).toBe('failed')
  })

  it('marks a pure connect (no attempts, no commands) as Probe', () => {
    const c = classifySession({ command_count: 0, login_success: false, auth_attempt_count: 0 })
    expect(c.kind).toBe('probe')
  })
})
