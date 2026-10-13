<script setup lang="ts">
  /** Hero figure must use proportional fonts, not tabular-nums, to maintain visual hierarchy. */
  import { computed, ref, useTemplateRef, watch } from 'vue'
  import Sparkline from '@/components/charts/Sparkline.vue'

  const {
    label,
    value,
    spark,
    short,
    glass = false,
  } = defineProps<{
    label: string
    /** Phone-width label; the full one is hidden there and the info dot carries the meaning. */
    short?: string
    value: string
    spark?: number[]
    glass?: boolean
  }>()

  // The info dot rides with the last word so it never floats alone on a wrapped label.
  const cut = computed(() => {
    const i = label.lastIndexOf(' ')
    return i < 0 ? Math.max(label.length - 1, 0) : i + 1
  })

  // The sparkline spans the tile's inner width without widening the tile: the wrapper
  // has no intrinsic width (contain: inline-size), so the svg is drawn at the measured one.
  const wrap = useTemplateRef<HTMLElement>('wrap')
  const sparkW = ref(96)
  // The wrapper only exists while spark has 2+ values, so observe it whenever it mounts.
  watch(
    wrap,
    (el, _, onCleanup) => {
      if (!el || typeof ResizeObserver === 'undefined') return
      const ro = new ResizeObserver(([e]) => {
        const w = Math.round(e?.contentRect.width ?? 0)
        if (w > 0) sparkW.value = w
      })
      ro.observe(el)
      onCleanup(() => ro.disconnect())
    },
    { flush: 'post', immediate: true },
  )
</script>

<template>
  <div class="stat-tile" :class="{ glass }">
    <div class="label-row">
      <span class="label"
        ><span :class="{ 'l-full': short }">{{ label.slice(0, cut) }}</span
        ><span class="tail"
          ><span :class="{ 'l-full': short }">{{ label.slice(cut) }}</span
          ><span v-if="short" class="l-short">{{ short }}</span
          ><slot name="label-extra" /></span
      ></span>
    </div>
    <span class="value">{{ value }}</span>
    <span v-if="$slots.meta" class="meta"><slot name="meta" /></span>
    <div v-if="spark && spark.length > 1" ref="wrap" class="spark">
      <Sparkline :values="spark" :w="sparkW" :h="16" />
    </div>
  </div>
</template>

<style scoped>
  /* Label, meta and spark rows add no intrinsic width, so the value alone sizes the tile.
     Children carry grid-row 1-4 (label, value, meta, spark) so a parent can lay tiles on a
     shared subgrid; flex ignores it. Subgrid parents must keep all four rows, even if one is empty. */
  .stat-tile {
    padding: 12px 16px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 0;
  }

  .stat-tile.glass {
    background: var(--glass);
    border-color: var(--glass-border);
    backdrop-filter: blur(14px) saturate(1.15);
    box-shadow: var(--shadow-md);
  }

  /* Strut size matches the label so wrapped lines stay tight. */
  .label-row {
    grid-row: 1;
    font-size: 11px;
    line-height: 1.3;
    contain: inline-size;
    align-self: stretch;
  }

  .tail {
    white-space: nowrap;
  }

  .tail :deep(button) {
    margin: -3px 0 -3px 4px;
    vertical-align: middle;
  }

  .label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-dim);
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .l-short {
    display: none;
  }

  @media (max-width: 480px) {
    .label {
      letter-spacing: 0.05em;
    }

    .l-full {
      display: none;
    }

    .l-short {
      display: inline;
    }
  }

  .spark {
    grid-row: 4;
    width: 100%;
    height: 16px;
    contain: inline-size;
    line-height: 0;
    opacity: 0.9;
  }

  .value {
    grid-row: 2;
    font-size: 26px;
    font-weight: 680;
    line-height: 1.15;
    letter-spacing: -0.01em;
    color: var(--text);
    overflow-wrap: anywhere;
  }

  .meta {
    grid-row: 3;
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 18px;
    contain: inline-size;
    align-self: stretch;
  }
</style>
