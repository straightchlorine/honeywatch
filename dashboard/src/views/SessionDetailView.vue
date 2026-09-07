<script setup lang="ts">
  import { computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import { getSessionByIdOptions } from '@/api/queries'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import SessionTerminal from '@/components/sessions/SessionTerminal.vue'

  const route = useRoute()
  const router = useRouter()
  const sessionId = computed(() => String(route.params.id ?? ''))

  const detailQ = useQuery(
    computed(() => getSessionByIdOptions({ path: { session_id: sessionId.value } })),
  )
  await detailQ.suspense()

  const session = computed(() => detailQ.data.value!)

  // Restore exact list state (sort, filters, page) when returning; router.back()
  // only works if list is in history, so fall back to /sessions for deep links.
  // Use history.state (not vue-router's stack) to detect the previous page.
  function goBack() {
    const back = window.history.state?.back
    const cameFromList = typeof back === 'string' && back.startsWith('/sessions') && !back.startsWith('/sessions/')
    if (cameFromList) {
      router.back()
    } else {
      router.push({ name: 'sessions' })
    }
  }
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="sessions" />
    </template>

    <div class="session-detail">
      <div class="page-head">
        <h1>Session replay</h1>
        <span class="sub">Everything the attacker typed, step by step.</span>
      </div>

      <button type="button" class="back" @click="goBack">&#8592; All sessions</button>
      <SessionTerminal :session="session" class="terminal-hero" />
    </div>
  </PageShell>
</template>

<style scoped>
  .session-detail {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1 1 auto;
    min-height: 0;
  }

  .page-head {
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex: none;
  }

  .page-head h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 700;
  }

  .sub {
    color: var(--text-dim);
    font-size: 13px;
  }

  .back {
    /* Use <button> for click handler, but style as a plain link. */
    appearance: none;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    font: inherit;

    flex: 0 0 auto;
    width: max-content;
    font-size: 13px;
    color: var(--text-muted);
    text-decoration: none;
  }

  .back:hover {
    color: var(--text);
  }

  .back:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-md);
  }

  .terminal-hero {
    flex: 1 1 auto;
    min-height: 0;
  }

  @media (max-width: 760px) {
    .page-head {
      flex-wrap: wrap;
      gap: 4px;
    }

    .page-head h1 {
      font-size: 22px;
      flex-basis: 100%;
    }

    .sub {
      flex-basis: 100%;
    }
  }
</style>
