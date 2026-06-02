<script setup lang="ts">
  import { computed, ref } from 'vue'
  import { fmtNumber } from '@/utils/format'
  import { useChoropleth } from './useChoropleth'
  import type { WorldGeometry } from './useWorldGeometry'
  import WorldMapLegend from './WorldMapLegend.vue'

  const props = defineProps<{
    geometry: WorldGeometry
    counts: Map<string, number>
  }>()

  const choropleth = computed(() => useChoropleth(props.counts))

  const nameById = computed(() => {
    const map = new Map<string, string>()
    for (const c of props.geometry.countries) map.set(c.id, c.name)
    return map
  })

  // Attacked countries, descending -- powers the aria summary + offscreen list.
  const ranked = computed(() => {
    const rows: { id: string; name: string; count: number }[] = []
    for (const [id, count] of props.counts) {
      if (count > 0) rows.push({ id, name: nameById.value.get(id) ?? id, count })
    }
    return rows.sort((a, b) => b.count - a.count)
  })

  const ariaLabel = computed(() => {
    if (!ranked.value.length) {
      return 'World map of honeypot attack origins. No attacks recorded yet.'
    }
    const top = ranked.value
      .slice(0, 5)
      .map((r) => `${r.name} ${fmtNumber(r.count)}`)
      .join(', ')
    return (
      `World map of honeypot attack origins. Top sources: ${top}. ` +
      `${ranked.value.length} countries with activity.`
    )
  })

  const frame = ref<HTMLElement | null>(null)
  interface Tip {
    name: string
    count: number
    x: number
    y: number
  }
  const tip = ref<Tip | null>(null)

  function position(ev: MouseEvent): { x: number; y: number } {
    const rect = frame.value?.getBoundingClientRect()
    return { x: ev.clientX - (rect?.left ?? 0), y: ev.clientY - (rect?.top ?? 0) }
  }

  function onEnter(id: string, ev: MouseEvent): void {
    tip.value = {
      name: nameById.value.get(id) ?? id,
      count: props.counts.get(id) ?? 0,
      ...position(ev),
    }
  }

  function onLeave(): void {
    tip.value = null
  }
</script>

<template>
  <figure class="world-map">
    <div ref="frame" class="frame">
      <svg
        class="svg"
        :viewBox="`0 0 ${geometry.width} ${geometry.height}`"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-label="ariaLabel"
      >
        <defs>
          <radialGradient id="map-ocean" cx="50%" cy="42%" r="75%">
            <stop offset="0%" stop-color="var(--map-ocean)" />
            <stop offset="100%" stop-color="var(--map-ocean-edge)" />
          </radialGradient>
        </defs>
        <path :d="geometry.sphere" fill="url(#map-ocean)" />
        <path class="graticule" :d="geometry.graticule" />
        <g>
          <!--
            The accessible data path is the role="img" summary above plus the
            offscreen <ul> below; the hover tooltip is mouse-only visual sugar,
            so the mouse-without-key-events / static-interaction rules don't
            apply here (the standard pattern for an SVG data-viz).
          -->
          <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
          <path
            v-for="c in geometry.countries"
            :key="c.id"
            class="country"
            :d="c.d"
            :fill="choropleth.fill(c.id)"
            @mouseenter="onEnter(c.id, $event)"
            @mouseleave="onLeave"
          />
          <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
        </g>
        <path class="borders" :d="geometry.borders" />
        <path class="coast" :d="geometry.coast" />
        <path class="sphere-outline" :d="geometry.sphere" />
      </svg>

      <div v-if="tip" class="tooltip" :style="{ transform: `translate(${tip.x}px, ${tip.y}px)` }">
        <span class="tip-name">{{ tip.name }}</span>
        <span class="tip-count">{{
          tip.count ? `${fmtNumber(tip.count)} sessions` : 'no activity'
        }}</span>
      </div>

      <div class="legend-overlay">
        <WorldMapLegend :max="choropleth.max" :ramp="choropleth.rampStops" />
      </div>
    </div>

    <ul class="visually-hidden">
      <li v-for="r in ranked" :key="r.id">{{ r.name }}: {{ fmtNumber(r.count) }} sessions</li>
    </ul>
  </figure>
</template>

<style scoped>
  .world-map {
    margin: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .frame {
    position: relative;
    flex: 1 1 auto;
    min-height: 240px; /* floor so the map stays legible when space is tight */
  }

  .svg {
    display: block;
    width: 100%;
    height: 100%; /* fill the frame; viewBox + preserveAspectRatio keeps it centered */
  }

  /* Legend floats in the map's dead bottom-left corner instead of taking a row,
   so the globe keeps the full height. */
  .legend-overlay {
    position: absolute;
    left: var(--space-2);
    bottom: var(--space-2);
    z-index: 1;
  }

  .country {
    transition: fill var(--motion-base) ease;
  }

  .country:hover {
    stroke: var(--accent);
    stroke-width: 0.75px;
    vector-effect: non-scaling-stroke;
  }

  .graticule {
    fill: none;
    stroke: var(--map-graticule);
    stroke-width: 0.5px;
    stroke-dasharray: 1 3;
    vector-effect: non-scaling-stroke;
  }

  .borders {
    fill: none;
    stroke: var(--map-border);
    stroke-width: 0.5px;
    vector-effect: non-scaling-stroke;
  }

  .coast {
    fill: none;
    stroke: var(--map-coast);
    stroke-width: 0.75px;
    vector-effect: non-scaling-stroke;
  }

  .sphere-outline {
    fill: none;
    stroke: var(--border);
    stroke-width: 1px;
    vector-effect: non-scaling-stroke;
  }

  .tooltip {
    position: absolute;
    top: 0;
    left: 0;
    margin: var(--space-3) 0 0 var(--space-3);
    padding: var(--space-1) var(--space-2);
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--bg-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-md);
    pointer-events: none;
    white-space: nowrap;
    z-index: 1;
  }

  .tip-name {
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    color: var(--text);
    font-weight: 600;
  }

  .tip-count {
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
</style>
