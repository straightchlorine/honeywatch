<script setup lang="ts">
  /**
   * Choropleth + city markers + sensor + live arcs, pan/zoom, hover tooltip,
   * keyboard selection. Geometry loads once; fills/selection update without reloading it.
   */
  import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'
  import type { MapCountryResponse, MapCityResponse } from '@/api/generated/types.gen'
  import { loadMapGeometry, type MapCountry } from './useMapGeometry'
  import { usePanZoom, type PanZoomState } from '@/composables/usePanZoom'
  import { useSeqScale } from '@/composables/useSeqScale'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import { useMapDetail } from '@/composables/useMapDetail'
  import { fmtNumber } from '@/utils/format'
  import { hexPoints } from '@/utils/hex'
  import { readStored, writeStored } from '@/utils/safeStorage'
  import MapControls from './MapControls.vue'
  import type { MapQualityLevel } from './MapQuality.vue'
  import CityDot from './CityDot.vue'
  import SelectionMarker from './SelectionMarker.vue'
  import SensorMarker from './SensorMarker.vue'

  const props = defineProps<{
    countries: MapCountryResponse[]
    cities: MapCityResponse[]
    selected?: string | null
    totalSessions: number
  }>()

  const emit = defineEmits<{
    select: [a2: string]
    deselect: []
  }>()

  // defineExpose must run before the top-level await (compiler constraint);
  // fireArc is only real once geometry loads via this forwarding indirection.
  let fireArcImpl: (a2: string, lat?: number | null, lon?: number | null) => void =
    () => {}
  let flyToCityImpl: (
    lat: number,
    lon: number,
    opts?: { city?: string; country_code?: string; sessions?: number },
  ) => void = () => {}
  defineExpose({
    fireArc: (a2: string, lat?: number | null, lon?: number | null) =>
      fireArcImpl(a2, lat, lon),
    flyToCity: (
      lat: number,
      lon: number,
      opts?: { city?: string; country_code?: string; sessions?: number },
    ) => flyToCityImpl(lat, lon, opts),
    clearCityFocus: () => {
      focusedCity.value = null
      selectedCityKey.value = null
    },
  })

  const geometry = await loadMapGeometry()

  const byA2 = computed(() => {
    const m = new Map<string, MapCountryResponse>()
    for (const c of props.countries) m.set(c.a2, c)
    return m
  })
  const maxSessions = computed(() => props.countries.reduce((m, c) => Math.max(m, c.sessions), 0))
  const scale = useSeqScale(() => maxSessions.value)

  const selectedCityKey = ref<string | null>(null)

  function fillFor(a2: string | null): string {
    const row = a2 ? byA2.value.get(a2) : undefined
    return row ? scale.color(row.sessions, 1.6) : 'var(--map-land)'
  }

  const svgEl = useTemplateRef('svg')
  const VIEW_KEY = 'hw-map-view'
  function loadView(): PanZoomState | undefined {
    try {
      const raw = readStored('sessionStorage', VIEW_KEY)
      return raw ? (JSON.parse(raw) as PanZoomState) : undefined
    } catch {
      return undefined
    }
  }
  // A phone shows the whole world as an unreadable thumbnail, so a first visit
  // opens over Europe instead. Only the opening view: the home button still
  // returns to the full world, and a stored view always wins.
  const MOBILE_OPEN = { lon: 15, lat: 48, k: 6 }
  function initialView(): PanZoomState | undefined {
    const saved = loadView()
    if (saved) return saved
    if (typeof window === 'undefined' || window.innerWidth > 900) return undefined
    const [px, py] = geometry.project(MOBILE_OPEN.lon, MOBILE_OPEN.lat)
    const k = MOBILE_OPEN.k
    return { k, tx: geometry.width / 2 - k * px, ty: geometry.height / 2 - k * py }
  }

  let saveTimer: ReturnType<typeof setTimeout> | undefined
  const { k, interacting, transform, reset, zoomIn, zoomOut, flyTo, handlers } = usePanZoom(svgEl, {
    minK: 1,
    maxK: 16,
    initial: initialView(),
    onChange: (s) => {
      clearTimeout(saveTimer)
      saveTimer = setTimeout(() => writeStored('sessionStorage', VIEW_KEY, JSON.stringify(s)), 250)
    },
    viewSize: () => ({ w: geometry.width, h: geometry.height }),
  })
  const cityScale = computed(() => 1 / Math.sqrt(k.value))

  // WCAG 2.5.8: 24x24 CSS px minimum tap target. City hits are sized in viewBox
  // units, so on-screen size depends on SVG render width and zoom; convert back
  // to maintain 12px (user units at current render width/zoom).
  const cssPerUnit = ref(1)
  let ro: ResizeObserver | null = null
  onMounted(() => {
    if (!svgEl.value) return
    ro = new ResizeObserver(([entry]) => {
      const w = entry?.contentRect.width ?? 0
      if (w) cssPerUnit.value = w / geometry.width
    })
    ro.observe(svgEl.value)
  })
  onBeforeUnmount(() => ro?.disconnect())
  // 12.2, not 12: the viewBox-to-CSS transform chain rounds the painted circle a
  // hair under, landing at 23.99997 CSS px and failing the 24px floor outright.
  const minHitR = computed(() => 12.2 / (cssPerUnit.value * k.value))

  // Hi-res geometry loaded past k=3 (base 0.53px at k=1 becomes 8.5px at k=16
  // on 1080p). Skipped on narrow viewports where base data never pixel-limits.
  // Coastline detail is viewer-chosen and persisted; smoothness depends on
  // machine and display size, not a heuristic (4K struggles with high tier).
  const QUALITY_KEY = 'hw-map-quality'
  const QUALITY_URL: Record<MapQualityLevel, string | null> = {
    low: null,
    regular: `${import.meta.env.BASE_URL}geo/countries-mid.json`,
    high: `${import.meta.env.BASE_URL}geo/countries-detail.json`,
  }
  const stored = readStored('localStorage', QUALITY_KEY) as MapQualityLevel | null
  const quality = ref<MapQualityLevel>(
    stored && stored in QUALITY_URL ? stored : 'high',
  )
  watch(quality, (q) => writeStored('localStorage', QUALITY_KEY, q))
  const detail = useMapDetail(k, geometry.fit, {
    threshold: 3,
    url: () => QUALITY_URL[quality.value],
    enabled: () => window.innerWidth >= 700,
  })

  function onZoomIn(): void {
    zoomIn(geometry.width / 2, geometry.height / 2)
  }
  function onZoomOut(): void {
    zoomOut(geometry.width / 2, geometry.height / 2)
  }
  function onReset(): void {
    reset()
    emit('deselect')
  }

  // Temporary "you are here" marker for a drawer-clicked city, since flyToCity
  // alone may land on an empty patch with no visual confirmation (city below
  // MAP_CITY_MIN_SESSIONS has no ambient dot). Cleared by parent or superseded
  // by the next flyToCity (keyed transition).
  const focusedCity = ref<{ x: number; y: number; key: string; r: number } | null>(null)

  function flyToCity(
    lat: number,
    lon: number,
    opts?: { city?: string; country_code?: string; sessions?: number },
  ): void {
    const [x, y] = geometry.project(lon, lat)
    flyTo(x, y, 8.5)

    let found = false
    if (opts?.city && opts?.country_code) {
      const match = cityMarks.value.find(
        (cm) => cm.city.city === opts.city && cm.city.country_code === opts.country_code,
      )
      if (match) {
        selectedCityKey.value = match.key
        found = true
      }
    }

    if (!found) {
      const sessions = opts?.sessions ?? 0
      const r = 1 + Math.sqrt(Math.min(sessions, 50) / 50) * 1.8
      focusedCity.value = { x, y, key: `${lat}-${lon}`, r }
    } else {
      focusedCity.value = null
    }
  }

  const tooltip = useHwTooltip()
  function onEnter(c: MapCountry, e: PointerEvent): void {
    // Touch taps select (drawer has details); hover bubble would linger over it.
    if (e.pointerType === 'touch') return
    showCountryTip(c)
    tooltip.move(e)
  }

  function showCountryTip(c: MapCountry): void {
    const row = c.a2 ? byA2.value.get(c.a2) : undefined
    const flag = c.a2 ? useCountryFlag(c.a2) : ''
    if (row) {
      tooltip.show(
        c.name,
        [
          ['Sessions', fmtNumber(row.sessions)],
          ['Unique IPs', fmtNumber(row.ips)],
          ['Share of attacks', pctShare(row.sessions)],
          ['Login success', row.success_rate === null ? 'n/a' : `${row.success_rate.toFixed(1)}%`],
        ],
        flag,
      )
    } else {
      tooltip.show(c.name, [['Sessions', 'none recorded']], flag)
    }
  }
  function pctShare(sessions: number): string {
    if (!props.totalSessions) return '0%'
    return `${((sessions / props.totalSessions) * 100).toFixed(1)}%`
  }
  function onMove(e: PointerEvent): void {
    tooltip.move(e)
  }
  // Tooltip on focus for keyboard users: aria-label can't carry IPs/share/auth data.
  function onFocus(c: MapCountry, e: FocusEvent): void {
    // Country paths are focusable, so a pointer press lands focus on whatever
    // is under the cursor - including a middle-button drag used only to pan.
    // Gate on :focus-visible so the ring and the tooltip are a keyboard
    // affordance, not something a pan leaves behind.
    const t = e.target as SVGGraphicsElement | null
    if (!t?.matches?.(':focus-visible')) return
    if (c.a2) focusedA2.value = c.a2
    const b = t.getBoundingClientRect?.()
    showCountryTip(c)
    if (b) tooltip.move({ clientX: b.left + b.width / 2, clientY: b.top } as PointerEvent)
  }
  function onBlur(): void {
    focusedA2.value = null
    tooltip.hide()
  }
  function onLeave(): void {
    tooltip.hide()
  }

  function onClick(c: MapCountry): void {
    if (c.a2 && byA2.value.has(c.a2)) emit('select', c.a2)
  }
  function onKeydown(c: MapCountry, e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick(c)
    }
  }
  // The selection/focus ring is drawn as a separate overlay pair rather than as
  // a stroke on the country itself: no single colour clears 4.5:1 against the
  // whole sequential ramp (measured minimum is 1.52:1 for near-black, 1.00:1
  // for --accent-hot against --seq-6, which is the same hex). A dark casing
  // under a bright ring always leaves one contrasting edge, whatever the fill.
  const focusedA2 = ref<string | null>(null)
  const ringD = computed(() => {
    const a2 = focusedA2.value ?? props.selected
    if (!a2) return null
    return geometry.countries.find((c) => c.a2 === a2)?.d ?? null
  })

  function ariaLabelFor(c: MapCountry): string {
    const row = c.a2 ? byA2.value.get(c.a2) : undefined
    return row ? `${c.name}: ${fmtNumber(row.sessions)} sessions` : c.name
  }

  // City markers use per-country normalization: each country's top city gets
  // the same radius regardless of total sessions in that country.
  interface CityMark {
    key: string
    x: number
    y: number
    r: number
    delay: number
    city: MapCityResponse & { _norm?: number }
  }

  const cityMarks = computed<CityMark[]>(() => {
    const byCountry = new Map<string, MapCityResponse[]>()
    for (const c of props.cities) {
      if (!byCountry.has(c.country_code)) byCountry.set(c.country_code, [])
      byCountry.get(c.country_code)!.push(c)
    }
    const normalized: (MapCityResponse & { _norm: number })[] = []
    for (const cities of byCountry.values()) {
      const max = cities[0]?.sessions ?? 1
      for (let i = 0; i < Math.min(5, cities.length); i++) {
        const c = cities[i]
        if (c) normalized.push({ ...c, _norm: c.sessions / max })
      }
    }
    return normalized.map((c, i) => {
      const [x, y] = geometry.project(c.lon, c.lat)
      const r = 1 + Math.sqrt(c._norm) * 1.7
      return {
        key: `${c.city}-${c.country_code}-${i}`,
        x,
        y,
        r,
        delay: (i * 0.4) % 3,
        city: c,
      }
    })
  })

  function onCityTooltipEnter(cityData: MapCityResponse, e: PointerEvent): void {
    tooltip.show(
      cityData.city,
      [['Sessions', fmtNumber(cityData.sessions)]],
      useCountryFlag(cityData.country_code),
    )
    tooltip.move(e)
  }
  function onCityTooltipMove(e: PointerEvent): void {
    tooltip.move(e)
  }
  function onCityTooltipLeave(): void {
    tooltip.hide()
  }
  // Clicking a dot also marks the dot itself, not just its country. Without
  // this `selectedCityKey` was only ever set by the drawer's fly-to, so a click
  // on the map produced the country outline and no acknowledgement at the point
  // actually clicked.
  function onCitySelect(countryCode: string, key: string): void {
    // Emit FIRST: the parent's select handler synchronously calls
    // clearCityFocus() when the country changes, which would wipe the key if we
    // set it beforehand.
    emit('select', countryCode)
    selectedCityKey.value = key
  }

  // Sensor marker: the honeypot lives in Helsinki.
  const sensor = geometry.project(24.94, 60.17)

  const helsinkiDot = computed<{ x: number; y: number; r: number } | null>(() => {
    const TOLERANCE = 12
    for (const mark of cityMarks.value) {
      const dist = Math.hypot(mark.x - sensor[0], mark.y - sensor[1])
      if (dist < TOLERANCE) {
        return { x: mark.x, y: mark.y, r: mark.r }
      }
    }
    return null
  })

  // Live arcs: imperative DOM + WAAPI, fire-and-forget outside Vue render cycle.
  const arcsGroup = useTemplateRef('arcsGroup')
  const reducedMotion = useReducedMotion()
  // One dot flies from where the connection came from to the sensor, then
  // fades out on arrival. Ambient, not an alert: it should register in
  // peripheral vision and never pull the eye off the map.
  const ARC_MS = 4400
  // Fraction of ARC_MS spent flying; the rest is the fade at the destination.
  const ARC_TRAVEL = 0.82
  const ARC_PEAK = 0.85
  const MAX_ARCS = 2
  let liveArcs = 0
  const SVGNS = 'http://www.w3.org/2000/svg'

  fireArcImpl = function fireArc(
    a2: string,
    lat?: number | null,
    lon?: number | null,
  ): void {
    if (reducedMotion.value || liveArcs >= MAX_ARCS) return
    // Prefer the session's own coordinates - the country centroid is a
    // stand-in, and for a wide country it starts the dot hundreds of km from
    // where the connection actually came from. Falls back when geo has no
    // city fix.
    const exact =
      typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)
        ? geometry.project(lon, lat)
        : null
    const country = exact ? null : geometry.countries.find((c) => c.a2 === a2)
    if (!exact && !country) return
    const [x1, y1] = exact ?? country!.centroid
    const [sx, sy] = sensor

    // Curve control point - a straight line across a projected map reads as a
    // UI element, a bowed one as a flight path.
    const cx = (x1 + sx) / 2
    const cy = Math.min(y1, sy) - Math.hypot(sx - x1, sy - y1) * 0.22

    const dot = document.createElementNS(SVGNS, 'circle')
    // Same 1/sqrt(k) compensation the city dots get - r is in user units inside
    // the zoom transform, so an uncompensated dot is a 25px blob at max zoom.
    // Sampled once at fire time, so zooming mid-flight leaves this dot's size stale.
    dot.setAttribute('r', String(1.8 * cityScale.value))
    dot.setAttribute('class', 'arc-dot')
    // Presentation attribute so the dot is already at its origin on the frame
    // it is appended; the animation below drives the CSS transform, which wins.
    dot.setAttribute('transform', `translate(${x1} ${y1})`)
    arcsGroup.value?.appendChild(dot)
    liveArcs++

    // WAAPI interpolates linearly between keyframes, so the samples are what
    // make the flight follow the curve rather than cut the corner.
    const STEPS = 24
    // Cumulative distance alongside each point: keyframe offsets spaced evenly
    // in the bezier parameter t would make the dot speed up and slow down,
    // because t is not linear in arc length.
    const pts: { x: number; y: number; d: number }[] = []
    let run = 0
    for (let i = 0; i <= STEPS; i++) {
      const t = i / STEPS
      const u = 1 - t
      const x = u * u * x1 + 2 * u * t * cx + t * t * sx
      const y = u * u * y1 + 2 * u * t * cy + t * t * sy
      const prev = pts[pts.length - 1]
      if (prev) run += Math.hypot(x - prev.x, y - prev.y)
      pts.push({ x, y, d: run })
    }
    const total = run || 1
    const frames = pts.map((p, i) => ({
      offset: (p.d / total) * ARC_TRAVEL,
      transform: `translate(${p.x}px, ${p.y}px)`,
      opacity: i === 0 ? 0 : ARC_PEAK,
    }))
    frames.push({ offset: 1, transform: `translate(${sx}px, ${sy}px)`, opacity: 0 })

    dot.animate(frames, { duration: ARC_MS }).addEventListener('finish', () => {
      dot.remove()
      liveArcs--
    })
  }

  flyToCityImpl = function flyToCityFn(
    lat: number,
    lon: number,
    opts?: { city?: string; country_code?: string },
  ): void {
    flyToCity(lat, lon, opts)
  }

  watch(
    () => props.selected,
    () => tooltip.hide(true),
  )

  onBeforeUnmount(() => clearTimeout(saveTimer))

  const ariaSummary = computed(() => {
    if (!props.countries.length) return 'World map of where attacks on the honeypot come from. No data yet.'
    const names = new Map(geometry.countries.map((c) => [c.a2, c.name]))
    const top = [...props.countries]
      .sort((a, b) => b.sessions - a.sessions)
      .slice(0, 5)
      // Full names, not alpha-2: a screen reader pronounces "CN" as a word.
      .map((c) => `${names.get(c.a2) ?? c.a2} ${fmtNumber(c.sessions)}`)
      .join(', ')
    return (
      `World map of where attacks on the honeypot come from. Top origins: ${top}. ` +
      'Disputed borders, such as the Line of Control in Kashmir, are drawn dotted.'
    )
  })
</script>

<template>
  <div class="deck">
    <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events -->
    <!-- role="img" forbids interactive descendants (axe: aria-prohibited-attr /
         nested-interactive) - the focusable country paths below need the
         ARIA Graphics Module's "graphics-document" role instead, which
         permits them. -->
    <svg
      ref="svg"
      class="worldmap"
      :class="{ panning: interacting }"
      role="graphics-document"
      :aria-label="ariaSummary"
      :viewBox="`0 0 ${geometry.width} ${geometry.height}`"
      @wheel="handlers.onWheel"
      @pointerdown="handlers.onPointerDown"
      @pointermove="handlers.onPointerMove"
      @pointerup="handlers.onPointerUp"
      @pointercancel="handlers.onPointerUp"
      @dblclick="handlers.onDblClick"
    >
      <defs></defs>
      <g :transform="transform">
        <path class="graticule" :d="geometry.graticule" aria-hidden="true" />
        <!-- SVG data-viz: pointer handlers without a static role are standard
             here - role/tabindex are set conditionally per country below,
             which the linter can't see through. -->
        <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/click-events-have-key-events -->
        <path
          v-for="c in geometry.countries"
          :key="c.id"
          class="country"
          :class="{ selected: !!c.a2 && c.a2 === selected }"
          :d="detail.get(c.id) ?? c.d"
          :fill="fillFor(c.a2)"
          :tabindex="c.a2 && byA2.has(c.a2) ? 0 : undefined"
          :role="c.a2 && byA2.has(c.a2) ? 'button' : undefined"
          :aria-label="c.a2 && byA2.has(c.a2) ? ariaLabelFor(c) : undefined"
          :aria-hidden="c.a2 && byA2.has(c.a2) ? undefined : 'true'"
          @pointerenter="onEnter(c, $event)"
          @pointermove="onMove"
          @pointerleave="onLeave"
          @focus="onFocus(c, $event)"
          @blur="onBlur"
          @click="onClick(c)"
          @keydown="onKeydown(c, $event)"
        />
        <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/click-events-have-key-events -->
        <!-- Boundaries Natural Earth does not class as settled: the Kashmir
             Line of Control, the Korean MDL, the Green Line, Abyei and the
             like. The casing is the load-bearing part - it is opaque and wider
             than the country stroke, so it OCCLUDES the solid border beneath
             rather than merely decorating it. A dotted line laid over an intact
             solid one reads as emphasis, not as "this is not agreed".
             Dots need no zoom compensation: non-scaling-stroke resolves the
             dash pattern in CSS px, measured constant from k=1 to k=16. -->
        <g class="disputed" aria-hidden="true">
          <path class="disputed-casing" :d="geometry.disputedBorders" />
          <path class="disputed-line" :d="geometry.disputedBorders" />
        </g>
        <!-- Selection/focus ring: dark casing under a bright ring, so one edge
             always contrasts whatever ramp colour is underneath. -->
        <template v-if="ringD">
          <path class="ring-casing" :d="ringD" aria-hidden="true" />
          <path class="ring" :d="ringD" aria-hidden="true" />
        </template>
        <polygon
          v-if="helsinkiDot"
          :points="hexPoints(0, 0, helsinkiDot.r * 3.5 * cityScale)"
          :transform="`translate(${helsinkiDot.x},${helsinkiDot.y})`"
          fill="var(--bg-0)"
          stroke="var(--accent-hot)"
          stroke-width="1"
          vector-effect="non-scaling-stroke"
          pointer-events="none"
          aria-hidden="true"
        />
        <g class="cities">
          <g v-for="ci in cityMarks" :key="ci.key">
            <CityDot
              :x="ci.x"
              :y="ci.y"
              :r="ci.r"
              :city="ci.city"
              :scale="cityScale"
              :min-hit-r="minHitR"
              @select="(cc: string) => onCitySelect(cc, ci.key)"
              @tooltip-enter="onCityTooltipEnter"
              @tooltip-move="onCityTooltipMove"
              @tooltip-leave="onCityTooltipLeave"
            />
            <transition :key="`ripple-${selectedCityKey}`" name="selection-fade">
              <SelectionMarker
                v-if="selectedCityKey === ci.key"
                :x="ci.x"
                :y="ci.y"
                :r="ci.r * cityScale"
              />
            </transition>
          </g>
        </g>
        <SensorMarker v-if="!helsinkiDot" :x="sensor[0]" :y="sensor[1]" />
        <!-- Fire-and-forget animation layer: every dot created into this
             inherits aria-hidden, so it can never leak into the a11y tree. -->
        <g ref="arcsGroup" class="arcs" aria-hidden="true" />
        <transition name="focus-fade">
          <SelectionMarker
            v-if="focusedCity"
            :key="focusedCity.key"
            :x="focusedCity.x"
            :y="focusedCity.y"
            :r="focusedCity.r * cityScale"
            :filled="true"
          />
        </transition>
      </g>
    </svg>
    <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events -->

    <MapControls
      :legend-max="fmtNumber(maxSessions)"
      v-model:quality="quality"
      @zoom-in="onZoomIn"
      @zoom-out="onZoomOut"
      @reset="onReset"
    />
  </div>
</template>

<style scoped>
  .deck {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    background:
      radial-gradient(1200px 700px at 50% 42%, rgba(245, 158, 11, 0.06), transparent 65%),
      var(--map-ocean);
  }

  .worldmap {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    cursor: grab;
    touch-action: none;
  }

  /* The class is on the svg itself, not a descendant. */
  .worldmap.panning {
    cursor: grabbing;
  }

  /* See usePanZoom's onWheel comment: suppressing hit-testing mid-gesture is
     what makes panning the hi-res tier feel smooth. */
  .worldmap.panning .country,
  .worldmap.panning .city-hit {
    pointer-events: none;
  }

  .graticule {
    fill: none;
    stroke: rgba(245, 158, 11, 0.05);
    vector-effect: non-scaling-stroke;
  }

  .country {
    stroke: var(--map-border);
    /* non-scaling-stroke in CSS px; 0.5px on HiDPI appears as hairline at 1x. */
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
    transition: filter var(--motion-fast);
  }

  @media (min-resolution: 1.5dppx) {
    .country {
      stroke-width: 0.5;
    }
  }

  .country:hover {
    filter: brightness(1.4);
  }

  .country.selected {
    filter: brightness(1.15);
  }

  .disputed {
    pointer-events: none;
  }
  .disputed path {
    fill: none;
    vector-effect: non-scaling-stroke;
  }
  /* The casing carries the SAME dash pattern as the line above it, so each dot
     gets a small dark halo instead of the whole boundary getting a continuous
     dark line. A solid casing occludes the border underneath more thoroughly,
     but it renders as a black gash across the fill and reads as far heavier
     than a settled border - the opposite of the intent. The base country
     stroke is only 0.38-alpha amber (about 1.2:1 against a hot fill), so the
     brighter dots dominate it without needing to paint it out. */
  .disputed-casing {
    stroke: var(--map-ocean);
    stroke-width: 1.7;
    stroke-dasharray: 0.1 3.6;
    opacity: 0.45;
  }
  .disputed-line {
    /* Dotted, not dashed: round caps on a near-zero dash read as a row of
       points, the convention for a boundary that is not finally agreed.
       --seq-7 rather than --accent-hot keeps it clear of the selection ring. */
    stroke: var(--seq-7);
    stroke-width: 0.75;
    stroke-dasharray: 0.1 3.6;
    opacity: 0.85;
  }

  .ring-casing,
  .ring {
    fill: none;
    pointer-events: none;
    vector-effect: non-scaling-stroke;
  }
  .ring-casing {
    stroke: var(--map-ocean-edge);
    stroke-width: 2.4;
    opacity: 0.5;
  }
  .ring {
    stroke: var(--accent-hot);
    stroke-width: 1.3;
  }

  /* bbox outline looks broken on irregular shapes; use the ring below instead. */
  .country:focus {
    outline: none;
  }
  /* The visible focus affordance is the .ring overlay above, which keeps its
     contrast against every fill in the ramp. */
  .country:focus-visible {
    stroke: var(--accent-hot);
    stroke-width: 1;
  }

  /* Glow soft enough to suggest depth rather than emit light: the map's own
     data is drawn in muted amber and a neon dot would dominate it. Opacity is
     driven by the animation, not set here. */
  .arcs :deep(.arc-dot) {
    fill: var(--accent-hot);
    filter: drop-shadow(0 0 3px var(--accent-glow));
    pointer-events: none;
  }

  .selection-fade-enter-active,
  .selection-fade-leave-active {
    transition: opacity var(--motion-slow);
  }
  .selection-fade-enter-from,
  .selection-fade-leave-to {
    opacity: 0;
  }

  .focus-fade-enter-active,
  .focus-fade-leave-active {
    transition: opacity var(--motion-slow);
  }
  .focus-fade-enter-from,
  .focus-fade-leave-to {
    opacity: 0;
  }
</style>
