<script setup lang="ts">
  // ErrorBoundary must wrap Suspense to catch errors from rejected views.
  import { useRoute } from 'vue-router'
  import LoadingState from './components/base/LoadingState.vue'
  import ErrorBoundary from './components/base/ErrorBoundary.vue'
  import { exitSplash } from './utils/splash'

  const route = useRoute()

  // Suspense also resolves once right after mount, while the first navigation is still
  // pending and no route has matched. Only a matched route means a view is on screen.
  function onResolve(): void {
    if (route.matched.length) exitSplash()
  }
</script>

<template>
  <ErrorBoundary>
    <RouterView v-slot="{ Component }">
      <Suspense :timeout="0" @resolve="onResolve">
        <component :is="Component" />
        <template #fallback>
          <LoadingState />
        </template>
      </Suspense>
    </RouterView>
  </ErrorBoundary>
</template>
