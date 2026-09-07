<script setup lang="ts">
  defineProps<{ min: string; max: string; noneLabel?: string }>()
</script>

<template>
  <div class="seq-legend">
    <span>{{ min }}</span>
    <div class="ramp" aria-hidden="true" />
    <span>{{ max }}</span>
    <span v-if="noneLabel" class="none">
      <span class="swatch" aria-hidden="true" />{{ noneLabel }}
    </span>
  </div>
</template>

<style scoped>
  .seq-legend {
    display: flex;
    align-items: center;
    gap: 8px;
    font: 500 11px var(--font-mono);
    color: var(--text-dim);
  }

  .ramp {
    width: 120px;
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--seq-1), var(--seq-3), var(--seq-5), var(--seq-7));
  }

  .none {
    margin-left: 8px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    background: var(--map-land);
    display: inline-block;
  }
</style>
