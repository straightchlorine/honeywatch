<script setup lang="ts">
  /**
   * Viewbox dimensions are measured via ResizeObserver (preserveAspectRatio
   * default "meet" would otherwise letterbox wide cards); ResizeObserver
   * callback not guaranteed on first paint (also no-op in jsdom tests).
   * Backend omits empty buckets, so client densifies into consecutive UTC days.
   */
  import { computed, onMounted, onUnmounted, ref, useTemplateRef } from 'vue'
  import type { ActivityBucketResponse } from '@/api/generated/types.gen'
  import { fmtNumber, fmtCompact } from '@/utils/format'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import EmptyState from '@/components/base/EmptyState.vue'

  const { buckets } = defineProps<{ buckets: ActivityBucketResponse[] }>()

  const tt = useHwTooltip()
  const reduced = useReducedMotion()

  const FALLBACK_W = 900
  const FALLBACK_H = 168
  const rootEl = useTemplateRef('root')
  const measuredWidth = ref(0)
  const measuredHeight = ref(0)
  const W = computed(() => measuredWidth.value || FALLBACK_W)
  const H = computed(() => measuredHeight.value || FALLBACK_H)
  const PLOT_L = 42
  const PLOT_R = computed(() => W.value - 8)
  const PLOT_T = 12
  const PLOT_B = computed(() => H.value - 22)

  function updateDimensions(): void {
    measuredWidth.value = rootEl.value?.clientWidth ?? 0
    measuredHeight.value = rootEl.value?.clientHeight ?? 0
  }

  const ro = new ResizeObserver(updateDimensions)
  onMounted(() => {
    updateDimensions()
    if (rootEl.value) ro.observe(rootEl.value)
  })
  onUnmounted(() => ro.disconnect())

  /** Fill missing days with count 0, capped at the last 31 so a huge gap
   *  cannot blow up the allocation. */
  function densifyBuckets(
    input: ActivityBucketResponse[]
  ): ActivityBucketResponse[] {
    if (input.length === 0) return []
    if (input.length === 1) return input

    const firstDate = new Date(input[0]!.bucket)
    const lastDate = new Date(input[input.length - 1]!.bucket)

    const byDate = new Map<string, number>()
    input.forEach((b) => {
      byDate.set(b.bucket.split('T')[0]!, b.count)
    })

    const result: ActivityBucketResponse[] = []
    const current = new Date(Date.UTC(firstDate.getUTCFullYear(), firstDate.getUTCMonth(), firstDate.getUTCDate()))
    const last = new Date(Date.UTC(lastDate.getUTCFullYear(), lastDate.getUTCMonth(), lastDate.getUTCDate()))

    for (
      ;
      current.getTime() <= last.getTime();
      current.setUTCDate(current.getUTCDate() + 1)
    ) {
      const dateStr = current.toISOString().split('T')[0]!
      const count = byDate.get(dateStr) ?? 0
      result.push({
        bucket: `${dateStr}T00:00:00+00:00`,
        count,
      })
    }

    if (result.length > 31) {
      return result.slice(-31)
    }

    return result
  }

  const densified = computed(() => densifyBuckets(buckets))

  /** Round the axis ceiling up to a "nice" 1/2/5 x 10^n step above the max. */
  function niceCeil(v: number): number {
    if (v <= 0) return 1
    const exp = Math.floor(Math.log10(v))
    const base = 10 ** exp
    const norm = v / base
    const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10
    return step * base
  }

  /** Compute the 90th percentile using nearest-rank method. */
  function percentile90(values: number[]): number {
    if (values.length === 0) return 0
    const sorted = [...values].sort((a, b) => a - b)
    const idx = Math.ceil(0.9 * sorted.length) - 1
    return sorted[Math.max(0, idx)] ?? 0
  }

  const rawMax = computed(() => densified.value.reduce((m, b) => Math.max(m, b.count), 0))

  const p90 = computed(() => {
    const counts = densified.value.map((b) => b.count)
    return percentile90(counts)
  })

  const isClamped = computed(() => {
    if (p90.value === 0 || rawMax.value === 0) return false
    return rawMax.value > 2.5 * p90.value
  })

  const axisMax = computed(() => {
    if (!isClamped.value) {
      return niceCeil(rawMax.value)
    }
    const clamped = niceCeil(p90.value * 1.5)
    if (clamped === 0 || clamped > rawMax.value) {
      return niceCeil(rawMax.value)
    }
    return clamped
  })

  const isEmpty = computed(() => densified.value.length === 0)

  const peakIdx = computed(() => {
    let idx = -1
    let best = -1
    densified.value.forEach((b, i) => {
      if (b.count > best) {
        best = b.count
        idx = i
      }
    })
    return idx
  })

  const gridLines = computed(() => {
    const top = axisMax.value
    const labels = [0, top / 2, top].map((v) => ({
      key: v,
      y: PLOT_B.value - (top > 0 ? (v / top) * (PLOT_B.value - PLOT_T) : 0),
      label: v === 0 ? '0' : fmtCompact(Math.round(v)),
    }))
    // Skip mid gridline if its label would duplicate the top label
    if (labels.length === 3) {
      const midLabel = labels[1]!.label
      const topLabel = labels[2]!.label
      if (midLabel === topLabel) {
        return [labels[0]!, labels[2]!]
      }
    }
    return labels
  })

  const slot = computed(() => (PLOT_R.value - PLOT_L) / Math.max(1, densified.value.length))

  const bars = computed(() => {
    const top = axisMax.value
    return densified.value.map((b, i) => {
      const clipped = b.count > top
      const displayCount = clipped ? top : b.count
      const barH = top > 0 ? (displayCount / top) * (PLOT_B.value - PLOT_T) : 0
      const x = PLOT_L + i * slot.value + slot.value * 0.18
      const w = Math.min(24, slot.value * 0.64)
      const barY = PLOT_B.value - barH
      // Prevent ascenders from clipping above viewBox; enforce minimum 9px from top
      const peakLabelY = Math.max(barY - 7, 9)
      const clipMarkerY = PLOT_B.value - barH
      return {
        key: `${b.bucket}-${i}`,
        x,
        y: barY,
        w,
        h: barH,
        peak: i === peakIdx.value,
        clipped,
        peakLabelY,
        clipMarkerY,
        dateLabel: fmtDate(b.bucket),
        title: `${fmtDate(b.bucket)} - ${fmtNumber(b.count)} sessions`,
        count: b.count,
        dateAnchor:
          i === 0 ? 'start' : i === densified.value.length - 1 ? 'end' : 'middle',
      }
    })
  })

  const xLabelIdx = computed(() => {
    const n = densified.value.length
    if (!n) return new Set<number>()
    return new Set([0, Math.floor((n - 1) / 2), n - 1])
  })

  const ariaLabel = computed(() => {
    if (!densified.value.length) return 'Daily session counts. No sessions recorded yet.'
    const peak = densified.value[peakIdx.value]!
    let msg =
      `Daily session counts over ${densified.value.length} days. ` +
      `Peak ${fmtDate(peak.bucket)} with ${fmtNumber(peak.count)} sessions.`
    if (isClamped.value) {
      msg += ` Axis capped at ${fmtNumber(axisMax.value)}; ${fmtDate(peak.bucket)} exceeds it at ${fmtNumber(peak.count)} sessions.`
    }
    return msg
  })

  function fmtDate(iso: string): string {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  }

  function showTooltip(title: string, count: number, e: PointerEvent): void {
    tt.show(title, [['Sessions', fmtNumber(count)]])
    tt.move(e)
  }

  function barDelay(i: number): string {
    return reduced.value ? '0ms' : `${i * 20}ms`
  }
</script>

<template>
  <!-- ResizeObserver target must persist across isEmpty toggle (unlike figure) -->
  <div ref="root" class="daily-columns">
    <EmptyState v-if="isEmpty" title="No activity yet" />
    <figure v-else class="daily-figure" role="img" :aria-label="ariaLabel">
      <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
      <svg :viewBox="`0 0 ${W} ${H}`" aria-hidden="true">
        <g v-for="g in gridLines" :key="`grid-${g.key}`">
          <line :x1="PLOT_L" :y1="g.y" :x2="PLOT_R" :y2="g.y" stroke="var(--grid-line)" stroke-width="1" />
          <text
            :x="PLOT_L - 8"
            :y="g.y + 3"
            text-anchor="end"
            fill="var(--text-dim)"
            font-size="10"
            font-family="var(--font-mono)"
          >
            {{ g.label }}
          </text>
        </g>

        <g v-for="(bar, i) in bars" :key="bar.key">
          <rect
            class="daily-bar"
            :x="bar.x"
            :y="bar.y"
            :width="bar.w"
            :height="bar.h"
            rx="3"
            :fill="bar.peak ? 'var(--accent)' : 'var(--series-1)'"
            :style="{ animationDelay: barDelay(i) }"
            @pointerenter="showTooltip(bar.title, bar.count, $event)"
            @pointermove="tt.move($event)"
            @pointerleave="tt.hide()"
          />
          <rect
            v-if="bar.clipped"
            :x="bar.x"
            :y="bar.clipMarkerY - 4"
            :width="bar.w"
            height="4"
            :fill="'var(--surface)'"
          />
          <text
            v-if="bar.peak || bar.clipped"
            :x="bar.x + bar.w / 2"
            :y="bar.peakLabelY"
            text-anchor="middle"
            fill="var(--text)"
            font-size="10.5"
            font-family="var(--font-mono)"
            font-weight="600"
          >
            {{ fmtNumber(bar.count) }}
          </text>
          <text
            v-if="xLabelIdx.has(i)"
            :x="bar.x + bar.w / 2"
            :y="H - 6"
            :text-anchor="bar.dateAnchor"
            fill="var(--text-dim)"
            font-size="10"
            font-family="var(--font-mono)"
          >
            {{ bar.dateLabel }}
          </text>
        </g>

        <text
          v-if="isClamped"
          :x="PLOT_R - 4"
          :y="PLOT_T + 10"
          text-anchor="end"
          fill="var(--text-dim)"
          font-size="10"
          font-family="var(--font-mono)"
        >
          axis capped
        </text>
      </svg>
      <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->

      <ul class="visually-hidden">
        <li v-for="bar in bars" :key="`sr-${bar.key}`">{{ bar.title }}</li>
      </ul>
    </figure>
  </div>
</template>

<style scoped>
  .daily-columns {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .daily-figure {
    margin: 0;
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
  }

  .daily-figure svg {
    flex: 1;
    min-height: 0;
    width: 100%;
  }

  .daily-bar {
    transition: filter var(--motion-fast);
    animation: bar-rise 280ms ease-out both;
  }

  .daily-bar:hover {
    filter: brightness(1.35);
  }

  @keyframes bar-rise {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .daily-bar {
      animation: none;
    }
  }
</style>
