// Client-side head sync for SPA navigation. The build-time prerender
// (scripts/prerender-seo.mjs) bakes the correct title/description/canonical
// into each route's index.html for crawlers that read raw HTML; this keeps
// them in sync once the SPA takes over and the user navigates between routes.
// Single source of the per-route values: src/seo/routes.json.
export const SITE_URL = 'https://honey.piotrkrzysztof.dev'

function setMeta(attr: 'name' | 'property', key: string, content: string): void {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.content = content
}

function setCanonical(href: string): void {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.rel = 'canonical'
    document.head.appendChild(el)
  }
  el.href = href
}

export function applyRouteHead(opts: {
  title: string
  description: string
  canonical: string
  noindex?: boolean
}): void {
  document.title = opts.title
  setMeta('name', 'description', opts.description)
  setMeta('property', 'og:title', opts.title)
  setMeta('property', 'og:description', opts.description)
  setMeta('property', 'og:url', opts.canonical)
  setMeta('name', 'twitter:title', opts.title)
  setMeta('name', 'twitter:description', opts.description)
  setCanonical(opts.canonical)
  // The SPA catch-all serves a soft 404 (HTTP 200), so tell crawlers not to
  // index unknown URLs rather than let them pile up as thin pages.
  setMeta('name', 'robots', opts.noindex ? 'noindex, follow' : 'index, follow')
}
