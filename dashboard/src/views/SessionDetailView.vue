<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/vue-query'
  import type { ListSessionsResponse } from '@/api/generated/types.gen'
  import { getSessionByIdOptions } from '@/api/queries'
  import { listSessionsOptions } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import SessionTerminal from '@/components/sessions/SessionTerminal.vue'
  import { sessionsListQuery } from '@/utils/pagination'

  const route = useRoute()
  const router = useRouter()
  const sessionId = computed(() => String(route.params.id ?? ''))

  const queryClient = useQueryClient()

  // Previous/Next swap the id on this instance; keepPreviousData holds the old session until the new one lands.
  const detailQ = useQuery(
    computed(() => ({
      ...getSessionByIdOptions({ path: { session_id: sessionId.value } }),
      placeholderData: keepPreviousData,
    })),
  )
  await detailQ.suspense()

  const session = computed(() => detailQ.data.value!)

  // Restore exact list state (sort, filters, page) when returning; router.back()
  // only works if list is in history, so fall back to /sessions for deep links.
  // Use history.state (not vue-router's stack) to detect the previous page.
  function listBack(): string | null {
    const back = window.history.state?.back
    const cameFromList = typeof back === 'string' && back.startsWith('/sessions') && !back.startsWith('/sessions/')
    return cameFromList ? back : null
  }

  // Neighbours come from the cached list page, rebuilt from the list URL's query. No cache, or
  // this session not on that page, means no links; the first/last row of a page has one neighbour.
  const nav = computed(() => {
    const back = listBack()
    if (!back) return null
    const q = new URL(back, window.location.origin).searchParams
    const opts = listSessionsOptions({ query: sessionsListQuery((k) => q.get(k) ?? undefined) })
    const page = queryClient.getQueryData<ListSessionsResponse>(opts.queryKey)
    const i = page?.items.findIndex((r) => r.id === sessionId.value) ?? -1
    if (!page || i < 0) return null
    return {
      row: page.items[i]!,
      position: i + 1,
      count: page.items.length,
      maxInterest: page.max_interest,
      prev: page.items[i - 1]?.id,
      next: page.items[i + 1]?.id,
    }
  })

  // Previous/Next only change the id on this instance, so nothing tells a screen reader the page
  // changed and focus would sit on a link that now points elsewhere (WCAG 4.1.3, 2.4.3).
  const heading = ref<HTMLElement | null>(null)
  const announcement = ref('')
  watch(sessionId, async () => {
    await nextTick()
    heading.value?.focus({ preventScroll: true })
    announcement.value = nav.value ? `Session ${nav.value.position} of ${nav.value.count} on this page` : ''
  })

  function goBack() {
    if (listBack()) {
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
        <h1 ref="heading" tabindex="-1">Session replay</h1>
        <span class="sub">What the honeypot recorded, step by step.</span>
      </div>

      <div class="session-nav">
        <button type="button" class="back" @click="goBack">&#8592; All sessions</button>
        <div v-if="nav && (nav.prev || nav.next)" class="pager">
          <!-- replace, not push: history.state.back must keep pointing at the list so
               Previous/Next can chain and "All sessions" is still one step back. -->
          <RouterLink
            v-if="nav.prev"
            :to="{ name: 'session-detail', params: { id: nav.prev } }"
            replace
            class="pager-link"
            >
Previous
</RouterLink
          >
          <span v-else class="pager-link disabled" aria-disabled="true">Previous</span>
          <RouterLink
            v-if="nav.next"
            :to="{ name: 'session-detail', params: { id: nav.next } }"
            replace
            class="pager-link"
            >
Next
</RouterLink
          >
          <span v-else class="pager-link disabled" aria-disabled="true">Next</span>
        </div>
      </div>
      <span class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</span>
      <SessionTerminal
        :session="session"
        :row="nav?.row"
        :max-interest="nav?.maxInterest"
        class="terminal-hero"
      />
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

  .session-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex: none;
  }

  .pager {
    display: flex;
    gap: 16px;
  }

  .pager-link {
    font-size: 13px;
    color: var(--text-muted);
    text-decoration: none;
  }

  .pager-link:hover {
    color: var(--text);
  }

  .pager-link.disabled,
  .pager-link.disabled:hover {
    color: var(--text-dim);
    opacity: 0.6;
    cursor: default;
  }

  h1:focus {
    outline: none;
  }

  .pager-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-md);
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

  /* Sized to its content; shrinks (and the log scrolls) once the viewport runs out. */
  .terminal-hero {
    flex: 0 1 auto;
    min-height: 0;
  }

  @media (max-width: 760px) {
    .pager-link {
      display: inline-flex;
      align-items: center;
      min-height: var(--control-h);
    }

    .back {
      display: inline-flex;
      align-items: center;
      min-height: var(--control-h);
    }

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
