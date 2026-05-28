<script setup lang="ts">
import AppShell from './components/layout/AppShell.vue'
import LoadingState from './components/base/LoadingState.vue'
</script>

<template>
  <AppShell>
    <RouterView v-slot="{ Component, route }">
      <Suspense :key="route.path" :timeout="0">
        <component :is="Component" />
        <template #fallback>
          <LoadingState />
        </template>
      </Suspense>
    </RouterView>
  </AppShell>
</template>
