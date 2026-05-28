<script setup lang="ts">
import PageHeader from '@/components/base/PageHeader.vue'
import EmptyState from '@/components/base/EmptyState.vue'
</script>

<template>
  <div class="credentials">
    <PageHeader title="Credentials" sub="Captured authentication attempts." />
    <EmptyState title="Coming soon." />
  </div>
</template>

<style scoped>
.credentials {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
