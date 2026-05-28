<script setup lang="ts">
  import { computed } from 'vue'

  type Size = 'sm' | 'md' | 'lg'

  const props = withDefaults(
    defineProps<{
      size?: Size
    }>(),
    { size: 'md' },
  )

  const sizeClass = computed(() => `size-${props.size}`)
</script>

<template>
  <span class="spinner" :class="sizeClass" role="status" aria-live="polite" aria-label="Loading">
    <span class="visually-hidden">Loading</span>
  </span>
</template>

<style scoped>
  .spinner {
    display: inline-block;
    border-radius: 50%;
    border-style: solid;
    border-color: var(--border);
    border-top-color: var(--accent);
    animation: spin 700ms linear infinite;
    box-sizing: border-box;
  }

  .size-sm {
    width: 14px;
    height: 14px;
    border-width: 2px;
  }

  .size-md {
    width: 20px;
    height: 20px;
    border-width: 2px;
  }

  .size-lg {
    width: 32px;
    height: 32px;
    border-width: 3px;
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

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: none;
      border-color: var(--border);
      background: var(--accent);
      border-top-color: var(--accent);
    }
  }
</style>
