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

  it('treats repeated (array) values as absent', () => {
    expect(
      sessionsListQuery((k) => (k === 'country' ? ['PL', 'DE'] : undefined)).country,
    ).toBeUndefined()
  })
})
