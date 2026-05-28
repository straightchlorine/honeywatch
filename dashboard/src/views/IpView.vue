<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '@/components/base/PageHeader.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const route = useRoute()
const ipHash = computed(() => String(route.params.hash ?? ''))
</script>

<template>
  <div class="ip">
    <PageHeader :title="`IP ${ipHash}`" sub="Activity from this source address." />
    <EmptyState title="Coming soon." />
  </div>
</template>

<style scoped>
.ip {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
