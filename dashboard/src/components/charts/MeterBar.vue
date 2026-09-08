<script setup lang="ts">
  /** Min-width ensures small percentages remain visually distinguishable. */
  import { computed } from 'vue'

  const { frac, fill = 'var(--series-1)' } = defineProps<{ frac: number; fill?: string }>()

  const widthPct = computed(() => Math.max(3, Math.min(100, Math.round(frac * 100))))
</script>

<template>
  <span class="meter-track">
    <span class="meter-fill" :style="{ width: widthPct + '%', background: fill }" />
  </span>
</template>

<style scoped>
  .meter-track {
    display: block;
    height: 8px;
    border-radius: 4px;
    background: var(--surface-2);
    overflow: hidden;
  }

  .meter-fill {
    display: block;
    height: 100%;
    min-width: 3px;
    border-radius: 0 4px 4px 0;
    animation: meter-fill 350ms ease-out both;
  }

  @keyframes meter-fill {
    from {
      width: 0;
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .meter-fill {
      animation: none;
    }
  }
</style>
