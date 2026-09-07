<script setup lang="ts">
  /**
   * Fallback marker shown when no Helsinki city dot exists in the data.
   */
  defineProps<{ x: number; y: number }>()
</script>

<template>
  <g aria-hidden="true" :transform="`translate(${x},${y})`" class="sensor">
    <path
      d="M0 -3.2 L2.7 -1.6 V1.6 L0 3.2 L-2.7 1.6 V-1.6 Z"
      fill="var(--bg-0)"
      stroke="var(--accent-hot)"
      stroke-width="1.2"
      vector-effect="non-scaling-stroke"
    />
    <circle r="0.9" fill="var(--accent-hot)" />
  </g>
</template>

<style scoped>
  .sensor {
    pointer-events: none;
  }
</style>
