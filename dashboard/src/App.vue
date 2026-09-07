<script setup lang="ts">
  // ErrorBoundary must wrap Suspense to catch errors from rejected views.
  import LoadingState from './components/base/LoadingState.vue'
  import ErrorBoundary from './components/base/ErrorBoundary.vue'
</script>

<template>
  <ErrorBoundary>
    <RouterView v-slot="{ Component }">
      <Suspense :timeout="0">
        <component :is="Component" />
        <template #fallback>
          <LoadingState />
        </template>
      </Suspense>
    </RouterView>
  </ErrorBoundary>
</template>
