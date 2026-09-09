<script setup lang="ts">
  /* User-driven quality tier: smooth pan depends on machine/display.
     Native <input type="range"> provides drag, swipe, keys, screen reader semantics. */
  import { computed } from 'vue'
  import { useHwTooltip } from '@/composables/useHwTooltip'

  export type MapQualityLevel = 'low' | 'regular' | 'high'

  const LEVELS: MapQualityLevel[] = ['low', 'regular', 'high']
  const LABEL: Record<MapQualityLevel, string> = {
    low: 'Low',
    regular: 'Regular',
    high: 'High',
  }

  const model = defineModel<MapQualityLevel>({ required: true })

  const tt = useHwTooltip()
  // Rows run in slider order (left to right), so the list reads the way the control moves.
  const TIP: [string, string][] = [
    ['Low', 'Blocky outlines, fastest'],
    ['Regular', 'Middle ground'],
    ['High', 'Sharpest, slowest to pan'],
  ]
  function showTip(): void {
    tt.show('Map detail', TIP)
  }

  const index = computed({
    get: () => LEVELS.indexOf(model.value),
    set: (i) => {
      model.value = LEVELS[Math.max(0, Math.min(LEVELS.length - 1, i))]!
    },
  })
</script>

<template>
  <div
    class="quality glass"
    @pointerenter="showTip"
    @pointermove="tt.move($event)"
    @pointerleave="tt.hide()"
    @focusin="showTip"
    @focusout="tt.hide()"
  >
    <!-- The caption is decorative: the input carries its own accessible name,
         so exposing the text twice would just make it read oddly. -->
    <span class="cap" aria-hidden="true">Map detail</span>
    <input
      v-model.number="index"
      class="slider"
      type="range"
      min="0"
      :max="LEVELS.length - 1"
      step="1"
      aria-label="Map detail"
      :aria-valuetext="LABEL[model]"
      list="map-quality-stops"
    />
    <datalist id="map-quality-stops">
      <option v-for="(l, i) in LEVELS" :key="l" :value="i" :label="LABEL[l]" />
    </datalist>
    <span class="val">{{ LABEL[model] }}</span>
  </div>
</template>

<style scoped>
  .quality {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
  }

  .cap {
    font: 650 9.5px var(--font-sans);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .val {
    /* Widest label "Regular" measures 40.42px here, so 44px is the real floor. */
    min-width: 44px;
    font: 650 10.5px var(--font-mono);
    color: var(--accent-hot);
  }

  .slider {
    width: 76px;
    height: 16px;
    margin: 0;
    background: transparent;
    cursor: pointer;
    -webkit-appearance: none;
    appearance: none;
  }

  .slider::-webkit-slider-runnable-track {
    height: 3px;
    border-radius: 2px;
    background: var(--glass-border);
  }

  .slider::-moz-range-track {
    height: 3px;
    border-radius: 2px;
    background: var(--glass-border);
  }

  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 11px;
    height: 11px;
    margin-top: -4px;
    border: none;
    border-radius: 50%;
    background: var(--accent-hot);
  }

  .slider::-moz-range-thumb {
    width: 11px;
    height: 11px;
    border: none;
    border-radius: 50%;
    background: var(--accent-hot);
  }

  .slider:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 3px;
  }

</style>
