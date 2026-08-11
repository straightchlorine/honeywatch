<script setup lang="ts">
  // ErrorBoundary wraps Suspense so rejected views have a mounted boundary to catch errors.
  import AppShell from './components/layout/AppShell.vue'
  import LoadingState from './components/base/LoadingState.vue'
  import ErrorBoundary from './components/base/ErrorBoundary.vue'
</script>

<template>
  <AppShell>
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
  </AppShell>
</template>
