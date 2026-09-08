<script setup lang="ts">
  /**
   * Selection indicator for a city with ring and ripples. Uses transform: scale()
   * for zoom-level consistency without SVG geometry recalculation.
   */
  import { useReducedMotion } from '@/composables/useReducedMotion'

  defineProps<{
    x: number
    y: number
    r: number
    filled?: boolean
  }>()

  const reducedMotion = useReducedMotion()

  // Two ripples with stagger; three feels too busy.
  const ripples = [0, 220]
</script>

<template>
  <g
    aria-hidden="true"
    :transform="`translate(${x},${y})`"
    class="selection-marker"
    pointer-events="none"
  >
    <circle v-if="filled" class="selection-filled" :r="r" />
    <circle class="selection-border" :r="r" />
    <template v-if="!reducedMotion">
      <circle
        v-for="(delay, i) in ripples"
        :key="`ripple-${i}`"
        class="selection-ripple"
        :r="r"
        :style="{ animationDelay: `${delay}ms` }"
      />
    </template>
  </g>
</template>

<style scoped>
  .selection-marker {
    pointer-events: none;
  }

  .selection-filled {
    fill: var(--text);
    opacity: 0;
    animation: fade-in 350ms ease-out forwards;
  }

  .selection-border {
    fill: none;
    stroke: var(--accent-hot);
    stroke-width: 1.2;
    opacity: 0.75;
    vector-effect: non-scaling-stroke;
  }

  .selection-ripple {
    fill: none;
    stroke: var(--accent-hot);
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
    animation: ripple 1100ms cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
  }

  @keyframes fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  /* Ends at opacity 0 to prevent lingering marker. */
  @keyframes ripple {
    0% {
      transform: scale(1);
      opacity: 0.65;
    }
    100% {
      transform: scale(3.4);
      opacity: 0;
    }
  }
</style>
