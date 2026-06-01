import { describe, expect, it } from 'vitest'

import { IP_BLOT, redactIps } from '@/utils/redactIps'

describe('redactIps', () => {
  it('masks an IPv4 literal inside a command', () => {
    const r = redactIps('wget http://34.11.136.102/meow')
    expect(r.count).toBe(1)
    expect(r.text).toBe('wget http://‹ip›/meow')
    expect(r.text).not.toContain('34.11.136.102')
  })

  it('masks IPv6 literals (full and compressed)', () => {
    expect(redactIps('ping 2001:db8::1').count).toBe(1)
    expect(redactIps('a 2001:0db8:0000:0000:0000:ff00:0042:8329 b').count).toBe(1)
    expect(redactIps('host ::1 ok').count).toBe(1)
  })

  it('does NOT mask non-IP tokens', () => {
    const negatives = [
      'chmod 777 meow',
      './meowarm64',
      '13:41:49',
      'SSH-2.0-Go',
      '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334',
    ]
    for (const s of negatives) {
      const r = redactIps(s)
      expect(r.count).toBe(0)
      expect(r.text).toBe(s)
    }
  })

  it('returns segments that reassemble to the redacted text', () => {
    const r = redactIps('a 1.2.3.4 b 5.6.7.8 c')
    expect(r.count).toBe(2)
    expect(r.segments.map((s) => s.text).join('')).toBe(r.text)
    expect(r.segments.filter((s) => s.redacted)).toHaveLength(2)
  })

  it('honors a custom token', () => {
    expect(redactIps('x 1.2.3.4', '[redacted]').text).toBe('x [redacted]')
  })

  it('leaves plain text untouched', () => {
    const r = redactIps('whoami')
    expect(r.count).toBe(0)
    expect(r.segments).toEqual([{ text: 'whoami', redacted: false }])
    expect(IP_BLOT).toBe('‹ip›')
  })
})
