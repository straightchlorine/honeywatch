<script setup lang="ts">
  /** Hero figure must use proportional fonts, not tabular-nums, to maintain visual hierarchy. */
  import Sparkline from '@/components/charts/Sparkline.vue'

  const {
    label,
    value,
    spark,
    glass = false,
  } = defineProps<{
    label: string
    value: string
    spark?: number[]
    glass?: boolean
  }>()
</script>

<template>
  <div class="stat-tile" :class="{ glass }">
    <div class="label-row">
      <span class="label">{{ label }}</span>
      <slot name="label-extra" />
    </div>
    <span class="value">{{ value }}</span>
    <Sparkline v-if="spark && spark.length > 1" :values="spark" :w="96" :h="16" class="spark" />
    <slot v-else name="meta-inline" />
    <span v-if="$slots.meta" class="meta"><slot name="meta" /></span>
  </div>
</template>

<style scoped>
  .stat-tile {
    padding: 12px 16px 10px;
    border-radius: var(--radius-lg);
    background: var(--surface);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 0;
  }

  .stat-tile.glass {
    background: var(--glass);
    border-color: var(--glass-border);
    backdrop-filter: blur(14px) saturate(1.15);
    box-shadow: var(--shadow-md);
  }

  .label-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .spark {
    display: block;
    width: 100%;
    margin: 0 auto;
    opacity: 0.9;
  }

  .value {
    font-size: 26px;
    font-weight: 680;
    line-height: 1.15;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .meta {
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 18px;
  }
</style>
