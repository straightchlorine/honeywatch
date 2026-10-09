<script setup lang="ts">
  import { computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/vue-query'
  import type { ListSessionsData, ListSessionsResponse } from '@/api/generated/types.gen'
  import { getSessionByIdOptions } from '@/api/queries'
  import { listSessionsOptions } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import SessionTerminal from '@/components/sessions/SessionTerminal.vue'

  const route = useRoute()
  const router = useRouter()
  const sessionId = computed(() => String(route.params.id ?? ''))

  const queryClient = useQueryClient()

  // keepPreviousData: Previous/Next swap the id on this same instance, so hold the old
  // session on screen until the neighbour arrives instead of rendering undefined.
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

  // Must equal SessionsView's page size, or the query key misses its cache.
  const LIST_PER_PAGE = 40
  type ListQuery = NonNullable<ListSessionsData['query']>

  // Neighbours come from the list page already in the cache (no fetch). Rebuilds the
  // exact query SessionsView ran from the list URL. Nothing cached, or this session
  // not on that page: no links.
  // ponytail: no cross-page stepping - the first/last row of a page has one neighbour only.
  const nav = computed(() => {
    const back = listBack()
    if (!back) return null
    const q = new URL(back, window.location.origin).searchParams
    const term = q.get('q') ?? ''
    const sha = q.get('sha256') ?? ''
    const opts = listSessionsOptions({
      query: {
        page: Math.max(1, parseInt(q.get('page') ?? '', 10) || 1),
        per_page: LIST_PER_PAGE,
        sort: (q.get('sort') as ListQuery['sort']) || 'interest',
        order: (q.get('order') as ListQuery['order']) || undefined,
        has: q.get('has') || undefined,
        country: q.get('country') || undefined,
        q: term.length >= 2 ? term : undefined,
        sha256: /^[0-9a-f]{64}$/.test(sha) ? sha : undefined,
      },
    })
    const page = queryClient.getQueryData<ListSessionsResponse>(opts.queryKey)
    const i = page?.items.findIndex((r) => r.id === sessionId.value) ?? -1
    if (!page || i < 0) return null
    return {
      row: page.items[i]!,
      maxInterest: page.max_interest,
      prev: page.items[i - 1]?.id,
      next: page.items[i + 1]?.id,
    }
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
        <h1>Session replay</h1>
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
          <RouterLink
            v-if="nav.next"
            :to="{ name: 'session-detail', params: { id: nav.next } }"
            replace
            class="pager-link"
            >
Next
</RouterLink
          >
        </div>
      </div>
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
