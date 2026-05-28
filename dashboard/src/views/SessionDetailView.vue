<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { getSessionByIdOptions } from '@/api/queries'

const route = useRoute()
const sessionId = computed(() => String(route.params.id ?? ''))

const detail = useQuery(
  computed(() => getSessionByIdOptions({ path: { session_id: sessionId.value } })),
)

await detail.suspense()
</script>

<template>
  <div class="session-detail">
    <header class="session-detail-head">
      <h1 class="session-detail-title">Session {{ sessionId }}</h1>
    </header>

    <pre class="payload">{{ JSON.stringify(detail.data.value, null, 2) }}</pre>
  </div>
</template>

<style scoped>
.session-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.session-detail-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-detail-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  font-family: var(--font-mono);
}

.payload {
  background: var(--bg-2);
  padding: var(--space-3);
  border-radius: var(--radius, 6px);
  font-family: var(--font-mono);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  overflow: auto;
  margin: 0;
}
</style>
