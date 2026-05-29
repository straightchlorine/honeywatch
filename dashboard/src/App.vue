<script setup lang="ts">
import AppShell from './components/layout/AppShell.vue'
import LoadingState from './components/base/LoadingState.vue'
import ErrorBoundary from './components/base/ErrorBoundary.vue'
</script>

<!--
  ErrorBoundary wraps <Suspense>, not the other way round: a suspended view that
  rejects during setup must surface in a boundary that has already mounted.
  Per-view boundaries inside a suspended component never catch the initial load.
-->
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
