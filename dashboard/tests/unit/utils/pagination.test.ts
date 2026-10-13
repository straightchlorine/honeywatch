import { describe, expect, it } from 'vitest'
import { SESSIONS_PER_PAGE, sessionsListQuery } from '@/utils/pagination'

const fromUrl = (qs: string) => {
  const p = new URLSearchParams(qs)
  return sessionsListQuery((k) => p.get(k) ?? undefined)
}

describe('sessionsListQuery', () => {
  it('defaults to page 1, interest sort, no filters', () => {
    expect(fromUrl('')).toEqual({
      page: 1,
      per_page: SESSIONS_PER_PAGE,
      fold: true,
      sort: 'interest',
      order: undefined,
      has: undefined,
      country: undefined,
      q: undefined,
      sha256: undefined,
    })
  })

  it('passes sort, order, has, country and page through', () => {
    const q = fromUrl('sort=recent&order=asc&has=commands,success&country=PL&page=3')
    expect(q).toMatchObject({
      sort: 'recent',
      order: 'asc',
      has: 'commands,success',
      country: 'PL',
      page: 3,
    })
  })

  it('clamps a bad page to 1', () => {
    expect(fromUrl('page=abc').page).toBe(1)
    expect(fromUrl('page=0').page).toBe(1)
  })

  it('ignores a search term under 2 chars', () => {
    expect(fromUrl('q=a').q).toBeUndefined()
    expect(fromUrl('q=ab').q).toBe('ab')
  })

  it('drops a malformed sha256 and keeps a valid one', () => {
    expect(fromUrl('sha256=XYZ').sha256).toBeUndefined()
    const sha = 'a'.repeat(64)
    expect(fromUrl(`sha256=${sha}`).sha256).toBe(sha)
  })

  it('clamps a page past the API maximum', () => {
    expect(fromUrl('page=50000').page).toBe(50000)
    expect(fromUrl('page=99999').page).toBe(50000)
  })

  it('falls back to interest for an unknown sort', () => {
    expect(fromUrl('sort=bogus').sort).toBe('interest')
    expect(fromUrl('sort=duration').sort).toBe('duration')
  })

  it('keeps a has list only when every token is known', () => {
    expect(fromUrl('has=commands,tcpip').has).toBe('commands,tcpip')
    expect(fromUrl('has=commands,bogus').has).toBeUndefined()
    expect(fromUrl('has=commands,').has).toBeUndefined()
  })

  it('keeps has=none only on its own', () => {
    expect(fromUrl('has=none').has).toBe('none')
    expect(fromUrl('has=none,commands').has).toBeUndefined()
  })

  it('treats repeated (array) values as absent', () => {
    expect(
      sessionsListQuery((k) => (k === 'country' ? ['PL', 'DE'] : undefined)).country,
    ).toBeUndefined()
  })
})
