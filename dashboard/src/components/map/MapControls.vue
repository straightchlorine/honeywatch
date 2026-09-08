<script setup lang="ts">
  import SeqLegend from '../base/SeqLegend.vue'
  import MapQuality, { type MapQualityLevel } from './MapQuality.vue'

  defineProps<{ legendMax: string }>()
  const emit = defineEmits<{ zoomIn: []; zoomOut: []; reset: [] }>()
  const quality = defineModel<MapQualityLevel>('quality', { required: true })
</script>

<template>
  <div class="mapctl">
    <div class="zoombtns">
      <button type="button" aria-label="Zoom in" @click="emit('zoomIn')">+</button>
      <button type="button" aria-label="Zoom out" @click="emit('zoomOut')">&minus;</button>
      <button type="button" aria-label="Reset view" class="reset" @click="emit('reset')">
        &#8962;
      </button>
    </div>
    <MapQuality v-model="quality" />
    <div class="legend-card glass">
      <SeqLegend min="1" :max="legendMax" none-label="none" />
    </div>
  </div>
</template>

<style scoped>
  .mapctl {
    position: absolute;
    z-index: 10;
    right: 22px;
    bottom: 22px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 10px;
  }

  .zoombtns {
    display: flex;
    gap: 6px;
  }


  .zoombtns button {
    width: 32px;
    height: 32px;
    /* Compensates for varying glyph and text baseline metrics. */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    background: var(--glass);
    color: var(--text);
    font: 600 15px var(--font-mono);
    cursor: pointer;
  }

  .zoombtns button:hover {
    background: var(--surface-hover);
  }

  .zoombtns button.reset {
    font-size: 13px;
  }

  .legend-card {
    padding: 8px 12px;
    border-radius: var(--radius-md);
  }

  .glass {
    background: var(--glass);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(14px) saturate(1.15);
    box-shadow: var(--shadow-md);
  }

  @media (max-width: 900px) {
    /* Centred under the live feed, within thumb reach at the bottom of the screen. */
    .mapctl {
      left: 0;
      right: 0;
      top: auto;
      bottom: 12px;
      flex-direction: row;
      align-items: center;
      justify-content: center;
      flex-wrap: wrap;
    }
    .legend-card {
      display: none;
    }
  }
</style>
