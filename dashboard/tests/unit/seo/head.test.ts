import { beforeEach, describe, expect, it } from 'vitest'

import { applyRouteHead, SITE_URL } from '@/seo/head'

const meta = (attr: 'name' | 'property', key: string) =>
  document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
const canonical = () => document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')

describe('applyRouteHead', () => {
  beforeEach(() => {
    document.head.innerHTML = ''
    document.title = ''
  })

  it('writes title, description, canonical and social tags for a route', () => {
    applyRouteHead({
      title: 'Activity · Honeywatch',
      description: 'Time-series activity of SSH honeypot attacks.',
      canonical: `${SITE_URL}/activity`,
    })

    expect(document.title).toBe('Activity · Honeywatch')
    expect(meta('name', 'description')?.content).toBe(
      'Time-series activity of SSH honeypot attacks.',
    )
    expect(canonical()?.href).toBe(`${SITE_URL}/activity`)
    expect(meta('property', 'og:title')?.content).toBe('Activity · Honeywatch')
    expect(meta('property', 'og:url')?.content).toBe(`${SITE_URL}/activity`)
    expect(meta('name', 'twitter:description')?.content).toBe(
      'Time-series activity of SSH honeypot attacks.',
    )
    expect(meta('name', 'robots')?.content).toBe('index, follow')
  })

  it('marks the route noindex when asked (soft-404 catch-all)', () => {
    applyRouteHead({
      title: 'Page not found · Honeywatch',
      description: '',
      canonical: `${SITE_URL}/nope`,
      noindex: true,
    })

    expect(meta('name', 'robots')?.content).toBe('noindex, follow')
  })

  it('updates existing tags in place rather than appending duplicates', () => {
    const opts = { title: 'A', description: 'a', canonical: `${SITE_URL}/a` }
    applyRouteHead(opts)
    applyRouteHead({ title: 'B', description: 'b', canonical: `${SITE_URL}/b` })

    expect(document.head.querySelectorAll('meta[name="description"]')).toHaveLength(1)
    expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1)
    expect(meta('name', 'description')?.content).toBe('b')
    expect(canonical()?.href).toBe(`${SITE_URL}/b`)
  })
})
