<script setup lang="ts">
  import { computed } from 'vue'
  import { hexPoints } from '@/utils/hex'

  const { size = 20, filled = false } = defineProps<{ size?: number; filled?: boolean }>()
  const height = computed(() => Math.round(size * 1.1))
  const points = hexPoints(10, 11, 9)
</script>

<template>
  <svg :width="size" :height="height" viewBox="0 0 20 22" aria-hidden="true">
    <polygon v-if="filled" :points="points" fill="var(--accent)" />
    <template v-else>
      <polygon :points="points" fill="none" stroke="var(--accent)" stroke-width="1.6" />
      <circle cx="10" cy="11" r="3.2" fill="var(--accent)" />
    </template>
  </svg>
</template>
