<script setup lang="ts">
  import { computed } from 'vue'

  const props = withDefaults(
    defineProps<{
      lines?: number
      width?: string
      height?: string
    }>(),
    { lines: 3 },
  )

  const lineHeight = computed(() => props.height ?? '0.85rem')
  const lineWidth = computed(() => props.width ?? '100%')
</script>

<template>
  <div class="skeleton" role="status" aria-live="polite" aria-busy="true">
    <span class="visually-hidden">Loading</span>
    <div
      v-for="i in lines"
      :key="i"
      class="skeleton-line"
      :style="{ width: i === lines && lines > 1 ? '60%' : lineWidth, height: lineHeight }"
    />
  </div>
</template>

<style scoped>
  .skeleton {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: 100%;
  }

  .skeleton-line {
    border-radius: var(--radius-sm);
    background: linear-gradient(90deg, var(--bg-1) 0%, var(--surface-hover) 50%, var(--bg-1) 100%);
    background-size: 200% 100%;
    animation: shimmer 1400ms ease-in-out infinite;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .skeleton-line {
      animation: none;
      background: var(--surface);
    }
  }
</style>
