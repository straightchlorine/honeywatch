import { describe, expect, it } from 'vitest'
import { KNOWN_BENIGN, benignContent } from '@/utils/knownDigests'

describe('knownDigests', () => {
  it('every listed digest is the real sha256 of the text it claims', async () => {
    const plaintext: Record<string, string> = {
      'an empty file': '',
      'a single line break': '\n',
      'a single space': ' ',
      'a Windows-style line break': '\r\n',
      'the text "admin:admin"': 'admin:admin',
    }
    for (const [digest, label] of Object.entries(KNOWN_BENIGN)) {
      const bytes = new TextEncoder().encode(plaintext[label])
      const hash = await crypto.subtle.digest('SHA-256', bytes)
      const hex = [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('')
      expect(hex, `${label} digest mismatch`).toBe(digest)
    }
  })

  it('identifies the newline capture that ranks second in real data', () => {
    expect(
      benignContent('01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b'),
    ).toBe('a single line break')
  })

  it('is case-insensitive on the digest', () => {
    expect(
      benignContent('01BA4719C80B6FE911B091A7C05124B64EEECE964E09C058EF8F9805DACA546B'),
    ).toBe('a single line break')
  })

  it('returns null for a hash whose content is genuinely unknown', () => {
    expect(benignContent('a'.repeat(64))).toBeNull()
  })
})
