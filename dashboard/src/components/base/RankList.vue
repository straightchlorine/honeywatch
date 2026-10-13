<script setup lang="ts" generic="T">
  /**
   * Ranked list component for networks, SSH clients, hosts, etc.
   */
  import { computed, nextTick, ref, useTemplateRef, onMounted, onUnmounted, watch } from 'vue'
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
    badge?: string
    badgeClass?: 'amber' | 'dim' | 'ok' | 'bad'
    badgeTitle?: string
  }

  const {
    rows,
    labelWidth = '180px',
    badgeWidth = '60px',
    mono = false,
    fill = 'var(--series-1)',
    label = 'Ranked list',
  } = defineProps<{
    rows: RankRow[]
    labelWidth?: string
    badgeWidth?: string
    mono?: boolean
    fill?: string
    /** Accessible name for the scroller; exposed only while it overflows. */
    label?: string
  }>()

  const tt = useHwTooltip()

  const hasIcon = computed(() => rows.some((r) => r.icon))
  const hasBadge = computed(() => rows.some((r) => r.badge))

  // Optional icon, label, optional badge, the middle tracks, then the value.
  // Every column is a FIXED width except the bar track (1fr), so bars start at
  // the same x in every row. Never use `auto` or `minmax` here: each row is its
  // own grid, and content-sized columns resolve per-row -> misaligned bars.
  function gridCols(labelCol: string, middle: string[]): string {
    return [
      hasIcon.value ? '18px' : null,
      labelCol,
      hasBadge.value ? badgeWidth : null,
      ...middle,
      '62px',
    ]
      .filter(Boolean)
      .join(' ')
  }
  const cols = computed(() => gridCols(labelWidth, ['1fr']))

  // Phone: bar drops to its own full-width line under the label row.
  const colsSm = computed(() => gridCols('minmax(0, 1fr)', []))

  // Bottom fade only while there is more to scroll - never covers the last row.
  const el = useTemplateRef('root')
  const hiddenCount = ref(0)
  function checkMore(): void {
    const n = el.value
    if (!n) return
    const bottom = n.scrollTop + n.clientHeight
    const more = bottom < n.scrollHeight - 4
    n.classList.toggle('rk-more', more)
    // Rows not fully visible; display:none rows (offsetHeight 0) never count.
    hiddenCount.value = more
      ? Array.from(n.children).filter(
          (c) =>
            (c as HTMLElement).offsetHeight > 0 &&
            (c as HTMLElement).offsetTop + (c as HTMLElement).offsetHeight > bottom + 1,
        ).length
      : 0
  }

  watch(
    () => rows,
    () => void nextTick(checkMore),
  )

  const ro = new ResizeObserver(checkMore)
  onMounted(() => {
    checkMore()
    ro.observe(el.value!)
  })
  onUnmounted(() => {
    ro.disconnect()
  })
</script>

<template>
  <div class="rank-wrap">
    <!-- one tab stop per list (the scroller, only while it overflows, as a named region); rows are pointer-tooltip only. -->
    <div
      ref="root"
      class="rank-list"
      :tabindex="hiddenCount > 0 ? 0 : undefined"
      :role="hiddenCount > 0 ? 'region' : undefined"
      :aria-label="hiddenCount > 0 ? label : undefined"
      :style="{ '--rk-cols': cols, '--rk-cols-sm': colsSm }"
      @scroll.passive="checkMore"
    >
      <div
        v-for="(r, i) in rows"
        :key="`${i}:${r.label}`"
        class="rank-row"
        @pointerenter="tt.show(r.title ?? r.label)"
        @pointermove="tt.move($event)"
        @pointerleave="tt.hide()"
      >
        <span v-if="hasIcon" class="rk-icon">{{ r.icon }}</span>
        <span class="rk-label" :class="{ mono }"
          >{{ r.label
          }}<span v-if="r.title && r.title !== r.label" class="visually-hidden">
            ({{ r.title }})</span
          ></span
        >
        <span v-if="hasBadge" class="rk-badge">
          <span v-if="r.badge" class="badge" :class="r.badgeClass ?? 'dim'" :title="r.badgeTitle">{{
            r.badge
          }}</span>
        </span>
        <span class="rk-track">
          <span
            class="rk-fill"
            :style="{ width: Math.max(2, Math.round(r.frac * 100)) + '%', background: fill }"
          />
        </span>
        <span class="rk-value num">{{ r.value }}</span>
        <span v-if="r.sub" class="rk-sub">{{ r.sub }}</span>
      </div>
    </div>
    <p v-if="hiddenCount > 0" class="rk-caption">{{ hiddenCount }} more - scroll</p>
  </div>
</template>

<style scoped>
  .rank-wrap {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .rk-caption {
    flex: none;
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  .rank-list {
    position: relative;
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

  .rank-list:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -1px;
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
    font-size: 12px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 520px) {
    .rank-row {
      grid-template-columns: var(--rk-cols-sm);
      row-gap: 3px;
    }

    .rk-track {
      grid-row: 2;
      grid-column: 1 / -1;
    }

    .rk-sub {
      margin-top: 0;
    }
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
