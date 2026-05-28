<script setup lang="ts">
import { computed } from 'vue'
import Spinner from './Spinner.vue'

type Variant = 'inline' | 'block' | 'overlay'
type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    label?: string
    variant?: Variant
    size?: Size
  }>(),
  { label: 'Loading…', variant: 'block', size: 'md' },
)

const rootClass = computed(() => `loading loading-${props.variant}`)
</script>

<template>
  <div :class="rootClass" role="status" aria-live="polite">
    <Spinner :size="size" />
    <span class="loading-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.loading {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
}

.loading-block {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6) var(--space-5);
  width: 100%;
  min-height: 120px;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-3);
  background: color-mix(in srgb, var(--bg-0) 70%, transparent);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  border-radius: inherit;
  z-index: 10;
}

.loading-label {
  color: var(--text-muted);
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
  font-variant-numeric: tabular-nums;
}
</style>
