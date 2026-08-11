<script setup lang="ts">
  // Top-level await creates Suspense boundary; geometry loads once, counts update reactively.
  import { loadWorldGeometry } from './useWorldGeometry'
  import WorldMapView from './WorldMapView.vue'

  defineProps<{
    counts: Map<string, number>
  }>()

  // Forward country selection to page (routes to /countries?country=XX).
  const emit = defineEmits<{ select: [code: string] }>()

  const geometry = await loadWorldGeometry()
</script>

<template>
  <WorldMapView :geometry="geometry" :counts="counts" @select="emit('select', $event)" />
</template>
