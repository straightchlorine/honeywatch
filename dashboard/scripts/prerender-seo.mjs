// Post-build SEO prerender: stamp per-route metadata into static HTML files.
//
// The app is a client-rendered SPA—crawlers see only the shell. We generate
// per-route static HTML (dist/activity.html, etc.) so crawlers find the correct
// <title>, description, canonical, and og: tags in raw HTML before JS runs.
//
// Routes written as flat files (not dirs) to avoid trailing-slash redirects;
// nginx try_files $uri $uri.html ... serves them directly so /activity matches
// the canonical and sitemap (no redirect).
//
// Sitemap and route list sourced from src/seo/routes.json—they stay in sync.
import { readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const SITE_URL = 'https://honey.piotrkrzysztof.dev'
const DIST = resolve(process.cwd(), 'dist')
const ROUTES = JSON.parse(readFileSync(resolve(process.cwd(), 'src/seo/routes.json'), 'utf8'))

const escAttr = (s) =>
  s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const urlFor = (path) => (path === '/' ? `${SITE_URL}/` : `${SITE_URL}${path}`)

// Throws if tag missing so template drift fails the build instead of shipping stale meta.
function replaceTag(html, re, replacement, label) {
  if (!re.test(html)) throw new Error(`prerender: <${label}> tag not found in built index.html`)
  return html.replace(re, replacement)
}

function renderRoute(baseHtml, route) {
  const url = urlFor(route.path)
  const title = escAttr(route.seoTitle)
  const desc = escAttr(route.description)
  let html = baseHtml
  html = replaceTag(html, /<title>[\s\S]*?<\/title>/, `<title>${title}</title>`, 'title')
  html = replaceTag(
    html,
    /<meta[^>]*name="description"[^>]*>/,
    `<meta name="description" content="${desc}" />`,
    'meta description',
  )
  html = replaceTag(
    html,
    /<link[^>]*rel="canonical"[^>]*>/,
    `<link rel="canonical" href="${url}" />`,
    'link canonical',
  )
  html = replaceTag(
    html,
    /<meta[^>]*property="og:url"[^>]*>/,
    `<meta property="og:url" content="${url}" />`,
    'meta og:url',
  )
  html = replaceTag(
    html,
    /<meta[^>]*property="og:title"[^>]*>/,
    `<meta property="og:title" content="${title}" />`,
    'meta og:title',
  )
  html = replaceTag(
    html,
    /<meta[^>]*property="og:description"[^>]*>/,
    `<meta property="og:description" content="${desc}" />`,
    'meta og:description',
  )
  html = replaceTag(
    html,
    /<meta[^>]*name="twitter:title"[^>]*>/,
    `<meta name="twitter:title" content="${title}" />`,
    'meta twitter:title',
  )
  html = replaceTag(
    html,
    /<meta[^>]*name="twitter:description"[^>]*>/,
    `<meta name="twitter:description" content="${desc}" />`,
    'meta twitter:description',
  )
  return html
}

function writeRouteHtml(path, html) {
  const file = path === '/' ? 'index.html' : `${path.replace(/^\/+/, '')}.html`
  writeFileSync(join(DIST, file), html)
  return file
}

function buildSitemap(routes) {
  const urls = routes
    .map(
      (r) =>
        `  <url>\n    <loc>${urlFor(r.path)}</loc>\n` +
        `    <changefreq>${r.changefreq}</changefreq>\n` +
        `    <priority>${r.priority}</priority>\n  </url>`,
    )
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
}

const baseHtml = readFileSync(join(DIST, 'index.html'), 'utf8')

for (const route of ROUTES) {
  const html = renderRoute(baseHtml, route)
  const written = writeRouteHtml(route.path, html)
  console.log(`prerender: ${route.path} -> dist/${written}`)
}

writeFileSync(join(DIST, 'sitemap.xml'), buildSitemap(ROUTES))
console.log(`prerender: sitemap -> dist/sitemap.xml (${ROUTES.length} urls)`)
