<script setup lang="ts">
  import { computed } from 'vue'
  import { useRoute } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import { getSessionByIdOptions } from '@/api/queries'
  import PageHeader from '@/components/base/PageHeader.vue'
  import SessionTerminal from '@/components/sessions/SessionTerminal.vue'

  const route = useRoute()
  const sessionId = computed(() => String(route.params.id ?? ''))

  const detailQ = useQuery(
    computed(() => getSessionByIdOptions({ path: { session_id: sessionId.value } })),
  )
  await detailQ.suspense()

  const session = computed(() => detailQ.data.value!)
</script>

<template>
  <div class="session-detail">
    <PageHeader title="Session replay" sub="Reconstructed from captured events." />
    <RouterLink class="back" :to="{ name: 'sessions' }">← All sessions</RouterLink>
    <SessionTerminal :session="session" class="terminal-hero" />
  </div>
</template>

<style scoped>
  .session-detail {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    flex: 1 1 auto;
    min-height: 0;
  }

  .back {
    flex: 0 0 auto;
    width: max-content;
    font-size: var(--type-sm);
    color: var(--text-muted);
  }

  /* The terminal is the hero: fills the leftover height; its body scrolls. */
  .terminal-hero {
    flex: 1 1 auto;
    min-height: 0;
  }
</style>
