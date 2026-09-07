/**
 * Captures whose plaintext is known, and is not malware.
 *
 * A shell redirect that wrote nothing but a newline ranks second in the
 * specimen list, above most real droppers. Unmarked it reads as the #2 most
 * common payload, and its VirusTotal link invites a lookup of sha256("\n").
 *
 * Digests are verified by hashing the plaintext, never guessed - a wrong entry
 * here would excuse a real payload.
 */
export const KNOWN_BENIGN: Readonly<Record<string, string>> = Object.freeze({
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855: 'an empty file',
  '01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b': 'a single line break',
  '36a9e7f1c95b82ffb99743e0c5c4ce95d83c9a430aac59f84ef3cbfab6145068': 'a single space',
  '7eb70257593da06f682a3ddda54a9d260d4fc514f645237f5ca74b08f8da61a6': 'a Windows-style line break',
  '8da193366e1554c08b2870c50f737b9587c3372b656151c4a96028af26f51334': 'the text "admin:admin"',
})

/** Plaintext of a known-benign capture, or null when the content is unknown. */
export function benignContent(sha256: string): string | null {
  return KNOWN_BENIGN[sha256.toLowerCase()] ?? null
}
