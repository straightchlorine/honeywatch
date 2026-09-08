<script setup lang="ts" generic="T">
  /**
   * Ranked list component for networks, SSH clients, hosts, etc.
   */
  import { computed, useTemplateRef, onMounted, onUnmounted } from 'vue'
  import { useHwTooltip } from '@/composables/useHwTooltip'

  export interface RankRow {
    label: string
    value: string
    /** 0..1 share of the max - drives bar width. */
    frac: number
    /** Generated at render time (e.g. a flag) - never raw unicode in source. */
    icon?: string
    title?: string
    sub?: string
    /** Bar hit the capped axis - render a notch so it does not read as
     *  simply "the maximum". The row's `value` still carries the real number. */
    over?: boolean
    badge?: string
    badgeClass?: 'amber' | 'dim' | 'ok' | 'bad'
  }

  const {
    rows,
    labelWidth = '180px',
    badgeWidth = '60px',
    mono = false,
    fill = 'var(--series-1)',
    holdToShowTooltip = false,
  } = defineProps<{
    rows: RankRow[]
    labelWidth?: string
    badgeWidth?: string
    mono?: boolean
    fill?: string
    /** Opt-in ~3s delay before tooltip appears (prevents spam on dense sidebars). */
    holdToShowTooltip?: boolean
  }>()

  const tt = useHwTooltip()
  const HOLD_DELAY_MS = 3000
  let holdTimer: ReturnType<typeof setTimeout> | null = null
  function clearHoldTimer(): void {
    if (holdTimer !== null) {
      clearTimeout(holdTimer)
      holdTimer = null
    }
  }
  function showTooltip(text: string): void {
    clearHoldTimer()
    if (!holdToShowTooltip) {
      tt.show(text)
      return
    }
    holdTimer = setTimeout(() => {
      holdTimer = null
      tt.show(text)
    }, HOLD_DELAY_MS)
  }
  function hideTooltip(): void {
    clearHoldTimer()
    tt.hide()
  }

  const hasIcon = computed(() => rows.some((r) => r.icon))
  const hasBadge = computed(() => rows.some((r) => r.badge))

  // Every column is a FIXED width except the bar track (1fr), so bars start at
  // the same x in every row. Never use `auto` or `minmax` here: each row is its
  // own grid, and content-sized columns resolve per-row -> misaligned bars.
  const cols = computed(() =>
    [hasIcon.value ? '18px' : null, labelWidth, hasBadge.value ? badgeWidth : null, '1fr', '62px']
      .filter(Boolean)
      .join(' '),
  )

  // Bottom fade only while there is more to scroll - never covers the last row.
  const el = useTemplateRef('root')
  function checkMore(): void {
    const n = el.value
    if (n) n.classList.toggle('rk-more', n.scrollTop + n.clientHeight < n.scrollHeight - 4)
  }

  const ro = new ResizeObserver(checkMore)
  onMounted(() => {
    checkMore()
    ro.observe(el.value!)
  })
  onUnmounted(() => {
    ro.disconnect()
    clearHoldTimer()
  })
</script>

<template>
  <div
    ref="root"
    class="rank-list"
    :style="{ '--rk-cols': cols }"
    @scroll.passive="checkMore"
  >
    <div
      v-for="r in rows"
      :key="r.label"
      class="rank-row"
      tabindex="0"
      @pointerenter="showTooltip(r.title ?? r.label)"
      @pointermove="tt.move($event)"
      @pointerleave="hideTooltip()"
      @focus="showTooltip(r.title ?? r.label)"
      @blur="hideTooltip()"
    >
      <span v-if="hasIcon" class="rk-icon">{{ r.icon }}</span>
      <span class="rk-label" :class="{ mono }">{{ r.label }}</span>
      <span v-if="hasBadge" class="rk-badge">
        <span v-if="r.badge" class="badge" :class="r.badgeClass ?? 'dim'">{{ r.badge }}</span>
      </span>
      <span class="rk-track">
        <span
          class="rk-fill"
          :class="{ 'rk-over': r.over }"
          :style="{ width: Math.max(2, Math.round(r.frac * 100)) + '%', background: fill }"
        />
      </span>
      <span class="rk-value num">{{ r.value }}</span>
      <span v-if="r.sub" class="rk-sub">{{ r.sub }}</span>
    </div>
  </div>
</template>

<style scoped>
  .rank-list {
    overflow-y: auto;
    min-height: 0;
    scrollbar-width: thin;
    scrollbar-color: var(--border-strong) transparent;
    scrollbar-gutter: stable; /* scrollbar never covers the values column */
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding-right: 4px;
  }

  .rank-list.rk-more {
    mask-image: linear-gradient(#000 calc(100% - 22px), transparent);
  }

  .rank-row {
    display: grid;
    grid-template-columns: var(--rk-cols);
    gap: 9px;
    align-items: center;
    font-size: 12.5px;
    flex: none;
    border-radius: 4px;
    outline-offset: -1px;
  }

  .rank-row:focus-visible {
    outline: 2px solid var(--accent);
  }

  .rk-label {
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rk-label.mono {
    font-family: var(--font-mono);
  }

  /* spans are inline by default; without display:block the bar has zero height */
  .rk-over {
    border-right: 3px solid var(--surface);
  }

  .rk-track {
    display: block;
    height: 8px;
    border-radius: 4px;
    background: var(--surface-2);
    overflow: hidden;
  }

  .rk-fill {
    display: block;
    height: 100%;
    border-radius: 0 4px 4px 0;
  }

  .rk-value {
    text-align: right;
    color: var(--text);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12.5px;
  }

  .rk-sub {
    grid-column: 1 / -1;
    margin-top: -3px;
    font-size: 11px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 999px;
    font: 600 11px var(--font-mono);
    letter-spacing: 0.02em;
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .badge.amber {
    color: var(--accent-hot);
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.25);
  }
  .badge.ok {
    color: var(--ok);
    background: rgba(132, 204, 22, 0.1);
    border-color: rgba(132, 204, 22, 0.28);
  }
  .badge.bad {
    color: var(--bad);
    background: rgba(248, 113, 113, 0.09);
    border-color: rgba(248, 113, 113, 0.26);
  }
  .badge.dim {
    color: var(--text-dim);
    background: var(--surface-2);
    border-color: var(--border);
  }
</style>
