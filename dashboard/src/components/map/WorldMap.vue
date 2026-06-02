<script setup lang="ts">
  // Async wrapper: the top-level await on the TopoJSON fetch makes this a
  // Suspense boundary (see OverviewView). Geometry loads once; `counts` flows
  // through reactively and only the fills recolor on each poll.
  import { loadWorldGeometry } from './useWorldGeometry'
  import WorldMapView from './WorldMapView.vue'

  defineProps<{
    counts: Map<string, number>
  }>()

  const geometry = await loadWorldGeometry()
</script>

<template>
  <WorldMapView :geometry="geometry" :counts="counts" />
</template>
