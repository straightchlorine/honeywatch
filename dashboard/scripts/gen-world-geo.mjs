// One-shot codegen: build public/geo/countries.json, the world choropleth
// geometry, from Natural Earth "Admin 0 - Countries" 1:10m.
//
//   node scripts/gen-world-geo.mjs
//
// NOT a build step. Re-run only to bump the Natural Earth pin. The output is
// committed so the app carries no build-time geo dependency.
//
// Two point-of-view editions are combined:
//   * the GERMAN POV (..._deu) is the base. It is the only NE edition that
//     resolves every boundary this dashboard cares about the way the MaxMind
//     GeoLite2 alpha-2 codes we join on do: Crimea in Ukraine, Western Sahara
//     at full extent as EH, Kosovo as XK, Northern Cyprus inside CY,
//     Somaliland inside SO. The ISO POV leaves Crimea in no polygon at all.
//   * the ISO POV (..._iso) supplies the 11 dependency codes the German POV
//     folds into their parent state (French Guiana, Reunion, Svalbard, ...).
//     Their footprint is erased from the base before they are merged in, so no
//     two features overlap.
//
// Feature ids are ISO 3166-1 alpha-2 - the key the API joins on. The six NE
// features with no alpha-2 (military base areas, unclaimed desert, disputed
// reefs) keep their 3-letter NE ADM0_A3 code so every id stays unique; the
// renderer treats any non-two-letter id as unjoinable land.
//
// Antarctica is not emitted: the map drops it anyway (dead space on an
// attack-origin map), it is 4% of the payload, and its 180th-meridian seam
// degenerates under simplification - geoContains then returns true for every
// point on the globe while geoArea still looks sane.
import { Buffer } from 'node:buffer'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

import { geoContains } from 'd3-geo'
import iso from 'i18n-iso-countries'
import { feature } from 'topojson-client'

// Never track master: NE moves disputed boundaries between releases.
const NE_TAG = 'v5.1.2'
const MAPSHAPER = 'mapshaper@0.7.55'
// Douglas-Peucker beats Visvalingam here: it holds the extreme vertices that
// keep small enclaves (Ceuta, Melilla, the Macau peninsula, the Quneitra
// salient) inside the right country. 20% sits mid-band: 16% is the floor where
// the checks below start failing, 35% still passes, and weighted Visvalingam
// (mapshaper's default) needs 40% to match what DP does at 16%.
const SIMPLIFY = ['dp', '20%', 'keep-shapes']

const SOURCES = {
  deu: 'fc4d56c6bc256f779e0ba21579f81d64885f5296dba3c23c3e78a9b89a7aa0fb',
  iso: '60eb10aa951f5872507c9436937508b09be4b43dc9fa7aad7644f23ef12e1cad',
}
// Boundary LINES, same tag. Used only for the classes Natural Earth does not
// call settled, so the map can draw those dotted instead of asserting them with
// the same confidence as the France/Germany border.
const BOUNDARIES = {
  file: 'ne_10m_admin_0_boundary_lines_land',
  sha: '74d9c16229c095fde65943a9919e337682f044bcebccb120764f38edf3b70f4a',
}
// FCLASS_DE is Natural Earth's own classification under the German point of
// view - the same POV the country polygons come from - falling back to the
// default FEATURECLA where it has no opinion. These five are the classes that
// are NOT a settled international boundary. "Overlay limit" and "Lease limit"
// are deliberately absent: a UN buffer zone and the Baikonur lease are not
// contested boundaries.
const UNSETTLED = new Set([
  'Disputed (please verify)',
  'Indefinite (please verify)',
  'Line of control (please verify)',
  'Indeterminant frontier',
  'Unrecognized',
])
// Unsettled lines that sit on NO edge of our polygons, because the German POV
// resolved the territory into a single fill. Drawing them would paint a line
// through the middle of one country - the opposite of the point. The berm is
// the notable one: deu gives Western Sahara its full extent as EH, so the line
// of control cuts across the middle of a single EH fill (excluded by class
// below, since it is the only SAH/MAR feature classed Unrecognized).
const NO_EDGE = new Set([
  'SOL/SOM', // Somaliland, dissolved into SO
  'CNM/CYN', // Cyprus green line, Northern Cyprus dissolved into CY
  'KAZ/KAB', // Baikonur lease
  'CAN/USA', // Juan de Fuca, maritime
  'null/null', // Kuril Islands, offshore
  'SAH/MAR:Unrecognized', // the Moroccan berm, mid-EH
])
const BORDERS_OUT = fileURLToPath(new URL('../public/geo/borders-disputed.json', import.meta.url))
// Codes the German POV folds into a parent state; taken from the ISO POV.
const DEPENDENCIES = 'BQ,BV,CC,CX,GF,GP,MQ,RE,SJ,TK,YT'
const DROP = 'AQ'

// Disputed and easily-oversimplified places, as (lon, lat) -> expected id.
// Every one of these is a boundary a naive world-atlas build gets wrong, or an
// enclave that vanishes if simplification is turned up too far.
const POINTS = [
  ['Simferopol', 34.1, 44.95, 'UA'],
  ['Sevastopol', 33.53, 44.6, 'UA'],
  ['Kerch', 36.47, 45.35, 'UA'],
  ['Donetsk', 37.8, 48.0, 'UA'],
  ['Laayoune', -13.2, 27.15, 'EH'],
  ['Tifariti', -10.6, 26.15, 'EH'],
  ['Bir Anzarane', -14.45, 23.9, 'EH'],
  ['Pristina', 21.16, 42.66, 'XK'],
  ['Famagusta', 33.94, 35.12, 'CY'],
  ['Quneitra', 35.82, 33.13, 'SY'],
  ['Hargeisa', 44.06, 9.56, 'SO'],
  ['Sukhumi', 41.0, 43.0, 'GE'],
  ['Tiraspol', 29.64, 46.84, 'MD'],
  ['Stepanakert', 46.75, 39.82, 'AZ'],
  ['Srinagar', 74.8, 34.08, 'IN'],
  ['Gilgit', 74.31, 35.92, 'PK'],
  ['Aksai Chin', 79.0, 35.1, 'CN'],
  ['Taipei', 121.56, 25.03, 'TW'],
  ['Ramallah', 35.2, 31.9, 'PS'],
  ['Gaza', 34.47, 31.5, 'PS'],
  ['Ceuta', -5.32, 35.89, 'ES'],
  ['Melilla', -2.94, 35.29, 'ES'],
  ['Gibraltar', -5.348, 36.135, 'GI'],
  ['Hong Kong', 114.15, 22.35, 'HK'],
  ['Macau', 113.549, 22.198, 'MO'],
  ['Cayenne', -52.3, 4.9, 'GF'],
  ['Longyearbyen', 15.6, 78.2, 'SJ'],
  ['Kralendijk', -68.28, 12.15, 'BQ'],
  ['St-Denis', 55.45, -20.88, 'RE'],
  ['Stanley', -57.85, -51.7, 'FK'],
]
// Open ocean: a ring that loses its closure under simplification keeps a sane
// area but flips inside-out, and then swallows the globe (Japan does this at
// quantization=1e6, Antarctica at some simplification levels). Cheap canary.
const OCEAN = [
  [0, 0],
  [-30, 0],
  [-140, 0],
  [-25, 40],
  [80, -40],
  [-150, 40],
]

const OUT = fileURLToPath(new URL('../public/geo/countries.json', import.meta.url))
// Unsimplified twin, lazily fetched once the user zooms past what the base tier
// supports. Same source, same chain, same ids - only -simplify differs - so the
// two tiers are interchangeable path-for-path at runtime.
const OUT_DETAIL = fileURLToPath(new URL('../public/geo/countries-detail.json', import.meta.url))
// Middle quality step. The jump from the base tier straight to unsimplified is
// about 5x the path data, which is more than a large display can pan smoothly;
// this sits between them so the viewer has somewhere to land.
const OUT_MID = fileURLToPath(new URL('../public/geo/countries-mid.json', import.meta.url))
const SIMPLIFY_MID = ['dp', '55%', 'keep-shapes']
const WORK = join(tmpdir(), `hw-world-geo-${NE_TAG}`)

async function fetchSource(name, want) {
  const file = join(WORK, `${name}.geojson`)
  if (!existsSync(file)) {
    const url = `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/${NE_TAG}/geojson/${name}.geojson`
    process.stdout.write(`fetch ${url}\n`)
    const res = await fetch(url)
    if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`)
    writeFileSync(file, Buffer.from(await res.arrayBuffer()))
  }
  const got = createHash('sha256').update(readFileSync(file)).digest('hex')
  if (got !== want) {
    throw new Error(`${name} checksum mismatch: expected ${want}, got ${got}`)
  }
  return file
}

function assertAll(topology) {
  const fc = feature(topology, topology.objects.countries)
  const problems = []

  const ids = fc.features.map((f) => String(f.id))
  const dupes = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))]
  if (dupes.length) problems.push(`duplicate feature ids: ${dupes.join(', ')}`)

  // The renderer keys the country list on the id and joins the API's alpha-2
  // on it, so every ISO code must be drawable and every id must be unique.
  const present = new Set(ids)
  const missing = Object.keys(iso.getAlpha2Codes())
    .filter((a2) => iso.alpha2ToNumeric(a2) && a2 !== DROP)
    .filter((a2) => !present.has(a2))
  if (missing.length) problems.push(`ISO alpha-2 codes with no polygon: ${missing.join(', ')}`)

  for (const [name, lon, lat, want] of POINTS) {
    const hits = fc.features.filter((f) => geoContains(f, [lon, lat])).map((f) => String(f.id))
    if (hits.length !== 1 || hits[0] !== want) {
      problems.push(`${name} (${lon}, ${lat}): expected ${want}, got ${hits.join('+') || 'nothing'}`)
    }
  }

  for (const pt of OCEAN) {
    const hits = fc.features.filter((f) => geoContains(f, pt)).map((f) => String(f.id))
    if (hits.length) problems.push(`open ocean ${pt.join(',')} is inside ${hits.join('+')}`)
  }

  if (problems.length) {
    for (const p of problems) process.stderr.write(`FAIL ${p}\n`)
    throw new Error(`${problems.length} geometry check(s) failed - not writing ${OUT}`)
  }
  return fc.features.length
}

mkdirSync(WORK, { recursive: true })
const deu = await fetchSource('ne_10m_admin_0_countries_deu', SOURCES.deu)
const isoPov = await fetchSource('ne_10m_admin_0_countries_iso', SOURCES.iso)
const built = join(WORK, 'countries.json')
const builtDetail = join(WORK, 'countries-detail.json')
const builtMid = join(WORK, 'countries-mid.json')

const PIPELINE = [
  ['-i', deu, 'name=world'],
  ['-filter-fields', 'ISO_A2_EH,ADM0_A3,NAME'],
  ['-i', isoPov, 'name=deps'],
  ['-filter-fields', 'ISO_A2_EH,ADM0_A3,NAME', 'target=deps'],
  ['-filter', `${JSON.stringify(DEPENDENCIES)}.split(",").indexOf(ISO_A2_EH) > -1`, 'target=deps'],
  // Cut their footprint out of the base first, or France would cover French
  // Guiana twice and the point checks below would see two owners.
  ['-erase', 'source=deps', 'target=world'],
  ['-merge-layers', 'target=world,deps', 'force', 'name=countries'],
  // NE writes -99 for the six features with no ISO code; ADM0_A3 is unique.
  ['-each', 'key = ISO_A2_EH === "-99" ? ADM0_A3 : ISO_A2_EH', 'target=countries'],
  ['-filter', `key !== ${JSON.stringify(DROP)}`, 'target=countries'],
  // Largest part first, so the dissolve inherits "France" rather than
  // "Clipperton I." for the four codes NE splits across several features.
  ['-sort', 'this.area', 'descending', 'target=countries'],
  ['-dissolve', 'key', 'copy-fields=NAME', 'target=countries'],
  ['-rename-fields', 'name=NAME', 'target=countries'],
  ['-filter-fields', 'name,key', 'target=countries'],
  // Emit in decreasing detail: unsimplified, then mid, then base. mapshaper's
  // -simplify is cumulative on the same layer, so the order matters.
  ['-o', builtDetail, 'format=topojson', 'id-field=key', 'target=countries'],
  ['-simplify', ...SIMPLIFY_MID],
  ['-o', builtMid, 'format=topojson', 'id-field=key', 'target=countries'],
  ['-simplify', ...SIMPLIFY],
  ['-o', built, 'format=topojson', 'id-field=key', 'target=countries'],
].flat()

execFileSync('npx', ['--yes', MAPSHAPER, ...PIPELINE], {
  stdio: ['ignore', 'inherit', 'inherit'],
})

function finish(src, dest, label) {
  const topology = JSON.parse(readFileSync(src, 'utf8'))
  // id-field copies the field to the TopoJSON id but leaves it in properties.
  for (const geom of topology.objects.countries.geometries) delete geom.properties.key
  const json = JSON.stringify(topology)
  const count = assertAll(JSON.parse(json))
  writeFileSync(dest, json)
  process.stdout.write(
    `wrote ${dest}\n` +
      `  ${label}: ${count} features, ${POINTS.length} disputed-point checks passed\n` +
      `  ${statSync(dest).size} bytes raw, ${gzipSync(json, { level: 9 }).length} bytes gzipped\n`,
  )
  return topology
}

// Both tiers run the full assertion suite: the detail tier is what the map
// shows at high zoom, so a bad border there is exactly as wrong as in the base.
const base = finish(built, OUT, 'base')
const mid = finish(builtMid, OUT_MID, 'mid')
const detail = finish(builtDetail, OUT_DETAIL, 'detail')

// Disputed boundary lines are drawn dotted, over an opaque casing that occludes
// the solid country stroke underneath. The casing is what retracts the claim:
// a dotted line over an intact solid stroke reads as emphasis, not retraction.
const blFile = await fetchSource(BOUNDARIES.file, BOUNDARIES.sha)
const bl = JSON.parse(readFileSync(blFile, 'utf8'))
const cls = (f) => f.properties.FCLASS_DE ?? f.properties.FEATURECLA
const pairOf = (f) => `${f.properties.ADM0_A3_L}/${f.properties.ADM0_A3_R}`
const disputed = bl.features.filter(
  (f) =>
    UNSETTLED.has(cls(f)) &&
    !NO_EDGE.has(pairOf(f)) &&
    !NO_EDGE.has(`${pairOf(f)}:${cls(f)}`),
)
const dropped = bl.features.filter((f) => UNSETTLED.has(cls(f))).length - disputed.length
const blOut = join(WORK, 'borders-disputed.geojson')
writeFileSync(
  blOut,
  JSON.stringify({
    type: 'FeatureCollection',
    features: disputed.map((f) => ({ type: 'Feature', properties: {}, geometry: f.geometry })),
  }),
)
execFileSync(
  'npx',
  [
    '--yes',
    MAPSHAPER,
    '-i',
    blOut,
    'name=borders',
    // Same simplification as the base tier so the dots track the coastline the
    // base tier actually draws. The casing is far wider than the residual.
    '-simplify',
    ...SIMPLIFY,
    '-o',
    BORDERS_OUT,
    'format=topojson',
    'target=borders',
  ],
  { stdio: ['ignore', 'inherit', 'inherit'] },
)
const blJson = readFileSync(BORDERS_OUT, 'utf8')
process.stdout.write(
  `wrote ${BORDERS_OUT}\n` +
    `  ${disputed.length} unsettled boundary features (${dropped} excluded as sitting on no polygon edge)\n` +
    `  ${statSync(BORDERS_OUT).size} bytes raw, ${gzipSync(blJson, { level: 9 }).length} bytes gzipped\n`,
)
if (disputed.length < 40 || disputed.length > 100) {
  throw new Error(`unexpected unsettled boundary count ${disputed.length} - did NE reclassify?`)
}

// The tiers must be swappable path-for-path at runtime.
const ids = (t) => t.objects.countries.geometries.map((g) => String(g.id)).sort().join(',')
if (ids(base) !== ids(detail) || ids(base) !== ids(mid)) {
  throw new Error('geometry tiers disagree on feature ids')
}
