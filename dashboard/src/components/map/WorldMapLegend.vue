<script setup lang="ts">
import { computed } from 'vue'
import { fmtNumber } from '@/utils/format'

const props = defineProps<{
  max: number
  ramp: string[]
}>()

const gradient = computed(() => `linear-gradient(to right, ${props.ramp.join(', ')})`)
</script>

<template>
  <div v-if="max > 0" class="legend">
    <div class="scale">
      <div class="bar" :style="{ background: gradient }" aria-hidden="true" />
      <div class="ticks">
        <span>1</span>
        <span>{{ fmtNumber(max) }}</span>
      </div>
    </div>
    <div class="no-data">
      <span class="swatch" aria-hidden="true" />
      <span>no events</span>
    </div>
  </div>
</template>

<style scoped>
.legend {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-3);
  flex-wrap: wrap;
}

.scale {
  flex: 1;
  min-width: 140px;
  max-width: 260px;
}

.bar {
  height: 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.ticks {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-muted);
}

.no-data {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-dim);
}

.swatch {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-sm);
  background: var(--map-land);
  border: 1px solid var(--border);
}
</style>
