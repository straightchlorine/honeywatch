/**
 * Web Storage that tolerates not existing.
 *
 * `localStorage`/`sessionStorage` are absent under Node's jsdom without the
 * webstorage flag and throw outright in Safari private mode, so an unguarded
 * `.getItem` during setup takes the whole component down. Reads fall back to
 * null and writes are dropped; persistence is a nicety here, never a
 * correctness requirement.
 */
type StoreName = 'localStorage' | 'sessionStorage'

function store(name: StoreName): Storage | null {
  try {
    return (globalThis as unknown as Record<StoreName, Storage | undefined>)[name] ?? null
  } catch {
    return null
  }
}

export function readStored(name: StoreName, key: string): string | null {
  try {
    return store(name)?.getItem(key) ?? null
  } catch {
    return null
  }
}

export function writeStored(name: StoreName, key: string, value: string): void {
  try {
    store(name)?.setItem(key, value)
  } catch {
    // Not persisted; the caller always has a working in-memory default.
  }
}
