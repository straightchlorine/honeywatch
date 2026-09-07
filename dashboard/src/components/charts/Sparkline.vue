<script setup lang="ts">
  import { computed } from 'vue'

  const {
    values,
    w = 96,
    h = 26,
    color = 'var(--accent-dim)',
  } = defineProps<{
    values: number[]
    w?: number | string
    h?: number | string
    color?: string
  }>()

  const min = computed(() => Math.min(...values))
  const max = computed(() => Math.max(...values))

  const wNum = computed(() => (typeof w === 'number' ? w : 96))
  const hNum = computed(() => (typeof h === 'number' ? h : 26))

  function sx(i: number): number {
    if (values.length <= 1) return wNum.value / 2
    return (i / (values.length - 1)) * (wNum.value - 6) + 3
  }
  function sy(v: number): number {
    const span = max.value - min.value || 1
    return hNum.value - 4 - ((v - min.value) / span) * (hNum.value - 8)
  }

  const path = computed(() =>
    values.map((v, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(''),
  )
  const lastX = computed(() => sx(values.length - 1).toFixed(1))
  const lastY = computed(() => sy(values[values.length - 1] ?? 0).toFixed(1))
</script>

<template>
  <svg :width="w" :height="h" :viewBox="`0 0 ${wNum} ${hNum}`" aria-hidden="true" class="sparkline-svg">
    <path class="sparkline-path" :d="path" fill="none" :stroke="color" stroke-width="1.5" stroke-linejoin="round" />
    <circle
      class="sparkline-dot"
      :cx="lastX"
      :cy="lastY"
      r="2.6"
      fill="var(--accent)"
      stroke="var(--surface)"
      stroke-width="1.5"
    />
  </svg>
</template>

<style scoped>
  .sparkline-svg {
    display: block;
  }

  .sparkline-path,
  .sparkline-dot {
    animation: sparkline-in 300ms ease-out both;
  }

  @keyframes sparkline-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .sparkline-path,
    .sparkline-dot {
      animation: none;
    }
  }
</style>
