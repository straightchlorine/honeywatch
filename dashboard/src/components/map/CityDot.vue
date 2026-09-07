<script setup lang="ts">
  import { computed } from 'vue'
  import type { MapCityResponse } from '@/api/generated/types.gen'

  const props = defineProps<{
    x: number
    y: number
    r: number
    city: MapCityResponse
    scale: number
    /** Floor for the hit circle, in viewBox units - keeps the tap target >= 24 CSS px. */
    minHitR?: number
  }>()

  const emit = defineEmits<{
    select: [countryCode: string]
    'tooltip-enter': [city: MapCityResponse, event: PointerEvent]
    'tooltip-move': [event: PointerEvent]
    'tooltip-leave': []
  }>()

  function onEnter(e: PointerEvent): void {
    if (e.pointerType === 'touch') return
    emit('tooltip-enter', props.city, e)
  }

  function onMove(e: PointerEvent): void {
    emit('tooltip-move', e)
  }

  function onLeave(): void {
    emit('tooltip-leave')
  }

  function onClick(): void {
    if (props.city.country_code) emit('select', props.city.country_code)
  }

  function onKeydown(e: KeyboardEvent): void {
    if ((e.key === 'Enter' || e.key === ' ') && props.city.country_code) {
      e.preventDefault()
      emit('select', props.city.country_code)
    }
  }

  const hitR = computed(() => Math.max((props.r + 3) * props.scale, props.minHitR ?? 0))
</script>

<template>
  <g :transform="`translate(${x},${y})`">
    <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
    <circle
      class="city-hit"
      :r="hitR"
      :tabindex="0"
      role="button"
      :aria-label="`${city.city} (${city.country_code})`"
      @pointerenter="onEnter"
      @pointermove="onMove"
      @pointerleave="onLeave"
      @click="onClick"
      @keydown="onKeydown"
    />
    <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
    <circle class="city-dot" :r="r * scale" fill="#f3e5c4" />
  </g>
</template>

<style scoped>
  .city-hit {
    fill: transparent;
    pointer-events: all;
    cursor: pointer;
  }

  .city-dot {
    vector-effect: non-scaling-stroke;
    pointer-events: none;
  }
</style>
