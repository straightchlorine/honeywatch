import type { SessionSummaryResponse } from '@/api/generated/types.gen'

export type SessionClassKind = 'active' | 'login' | 'failed' | 'probe'

export interface SessionClass {
  kind: SessionClassKind
  label: string
  title: string
}

/**
 * Classify a session for at-a-glance browsing. Most captured sessions are
 * credential-stuffing with no shell activity, so the classification lets a
 * viewer skip the noise: "Active" marks the sessions actually worth opening.
 *
 * Priority (highest first): shell activity > a bare successful login > a failed
 * brute-force > a pure connect with no auth attempts.
 */
export function classifySession(
  s: Pick<SessionSummaryResponse, 'command_count' | 'login_success' | 'auth_attempt_count'>,
): SessionClass {
  if (s.command_count > 0) {
    const n = s.command_count
    // Label avoids "active" -- these sessions are over, not ongoing.
    return { kind: 'active', label: 'CLI', title: `${n} command${n === 1 ? '' : 's'} run` }
  }
  if (s.login_success) {
    return { kind: 'login', label: 'Login', title: 'Logged in, no commands run' }
  }
  if (s.auth_attempt_count > 0) {
    return { kind: 'failed', label: 'Failed auth', title: 'Login attempts, none succeeded' }
  }
  return { kind: 'probe', label: 'Probe', title: 'Connection only, no login attempts' }
}
