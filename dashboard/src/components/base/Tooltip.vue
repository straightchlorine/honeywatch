<script setup lang="ts">
  import { nextTick, ref, watch } from 'vue'

  /**
   * Themed, cursor-anchored tooltip bubble. Presentational only -- the parent owns
   * the state (see `useTooltip`). Teleports to <body> so it escapes any
   * `overflow: hidden` / stacking context on the chart container, and clamps
   * itself inside the viewport so it never spills off-screen near an edge.
   */
  const props = defineProps<{
    visible: boolean
    x: number
    y: number
    text?: string
  }>()

  const CURSOR_GAP = 14
  const EDGE_MARGIN = 8

  const bubble = ref<HTMLElement | null>(null)
  const left = ref(0)
  const top = ref(0)

  async function place(): Promise<void> {
    await nextTick()
    const el = bubble.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    const vw = window.innerWidth
    const vh = window.innerHeight
    // Center horizontally on the cursor, clamped inside the viewport.
    let l = props.x - w / 2
    l = Math.min(Math.max(l, EDGE_MARGIN), Math.max(EDGE_MARGIN, vw - w - EDGE_MARGIN))
    // Prefer above the cursor; drop below when there isn't room up top.
    let t = props.y - h - CURSOR_GAP
    if (t < EDGE_MARGIN) t = props.y + CURSOR_GAP
    if (t + h > vh - EDGE_MARGIN) t = Math.max(EDGE_MARGIN, vh - h - EDGE_MARGIN)
    left.value = l
    top.value = t
  }

  watch(
    () => [props.visible, props.x, props.y, props.text],
    () => {
      if (props.visible) void place()
    },
    { immediate: true },
  )
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      ref="bubble"
      class="tooltip"
      role="tooltip"
      :style="{ left: `${left}px`, top: `${top}px` }"
    >
      <slot>{{ text }}</slot>
    </div>
  </Teleport>
</template>

<style scoped>
  .tooltip {
    position: fixed;
    z-index: 60; /* above the sticky header (50); below the skip-link (100) */
    width: max-content;
    max-width: 260px;
    padding: var(--space-1) var(--space-2);
    background: var(--bg-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-md);
    color: var(--text);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-variant-numeric: tabular-nums;
    pointer-events: none; /* never eat the hover that spawned it (no flicker) */
    white-space: normal;
    overflow-wrap: anywhere;
  }
</style>
