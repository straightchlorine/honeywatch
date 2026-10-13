<script setup lang="ts">
  /**
   * Keyboard-focus ring for SVG hex marks: a 2px --bg-0 gap under a 3px
   * --accent-hot ring, drawn in a top layer so it never reads as a fill tint
   * and is never clipped by neighbours. Geometry: edge offsets of 1px / 3.5px,
   * i.e. hex radius + 1.16 / + 4.04 (offset / cos 30deg).
   */
  import { hexPoints } from '@/utils/hex'

  defineProps<{ cx: number; cy: number; r: number }>()
</script>

<template>
  <g aria-hidden="true">
    <polygon class="ring-gap" :points="hexPoints(cx, cy, r + 1.16)" />
    <polygon class="ring" :points="hexPoints(cx, cy, r + 4.04)" />
  </g>
</template>

<style scoped>
  .ring-gap,
  .ring {
    fill: none;
    stroke-linejoin: round;
    pointer-events: none;
  }

  .ring-gap {
    stroke: var(--bg-0);
    stroke-width: 2;
  }

  .ring {
    stroke: var(--accent-hot);
    stroke-width: 3;
  }
</style>
