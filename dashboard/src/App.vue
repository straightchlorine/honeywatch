<script setup lang="ts">
  // ErrorBoundary must wrap Suspense to catch errors from rejected views.
  import { useRoute } from 'vue-router'
  import LoadingState from './components/base/LoadingState.vue'
  import ErrorBoundary from './components/base/ErrorBoundary.vue'
  import { exitSplash, revealPage } from './utils/splash'

  const route = useRoute()
  // How long the old page stays up before the loader replaces it. Without this wait the
  // swap blanks the screen for the whole load: the loader itself only fades in later.
  const LOADER_WAIT_MS = 220
  // When the current page change started, so a slow one can end with the hexagon reveal.
  // Pending, not fallback: Vue fires pending on every page change, also for views that
  // render at once and never show the fallback, so the time is never left over.
  let pendingAt = 0

  // While the first-load splash is up there is no old page to wait on, so the loader keeps
  // its own delay.
  function splashUp(): boolean {
    return !!document.getElementById('hw-splash')
  }

  function onPending(): void {
    pendingAt = performance.now()
  }

  // Suspense also resolves once right after mount, while the first navigation is still
  // pending and no route has matched. Only a matched route means a view is on screen.
  // revealPage does nothing while the loading splash is still up, so it only acts on
  // later page changes.
  function onResolve(): void {
    if (!route.matched.length) return
    exitSplash()
    revealPage(performance.now() - pendingAt)
  }
</script>

<template>
  <ErrorBoundary>
    <RouterView v-slot="{ Component }">
      <Suspense :timeout="LOADER_WAIT_MS" @pending="onPending" @resolve="onResolve">
        <component :is="Component" />
        <template #fallback>
          <LoadingState :immediate="!splashUp()" />
        </template>
      </Suspense>
    </RouterView>
  </ErrorBoundary>
</template>
