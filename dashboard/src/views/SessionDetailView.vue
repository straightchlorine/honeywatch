<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/vue-query'
  import type { ListSessionsResponse, RunSessionsResponse } from '@/api/generated/types.gen'
  import { getSessionByIdOptions } from '@/api/queries'
  import {
    listRunSessionsOptions,
    listSessionsOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import SessionTerminal from '@/components/sessions/SessionTerminal.vue'
  import { SESSIONS_PER_PAGE, sessionsListQuery } from '@/utils/pagination'
  import { buildSequence } from '@/utils/sessionSequence'
  import { setLastViewed } from '@/utils/lastViewed'

  const route = useRoute()
  const router = useRouter()
  // This page stays mounted while the next one loads, after the route has already moved on. An
  // empty id would fetch /sessions/, the list, into this page's detail query, so keep the last id.
  const sessionId = computed<string>((prev) => {
    const id = route.params.id
    return typeof id === 'string' ? id : (prev ?? '')
  })

  const queryClient = useQueryClient()
  watch(sessionId, setLastViewed, { immediate: true })

  // Previous/Next swap the id on this instance; keepPreviousData holds the old session until the new one lands.
  const detailQ = useQuery(
    computed(() => ({
      ...getSessionByIdOptions({ path: { session_id: sessionId.value } }),
      placeholderData: keepPreviousData,
    })),
  )
  await detailQ.suspense()

  // Only a 404 means not-found; any other failure surfaces the real API error.
  const detailErr = detailQ.error.value as { code?: number } | null
  if (detailErr && detailQ.data.value === undefined && detailErr.code !== 404) throw detailErr

  // Undefined for an unknown id (404): suspense() resolves on error, so show a not-found state.
  const session = computed(() => detailQ.data.value)

  // Restore exact list state (sort, filters, page) when returning; router.back()
  // only works if list is in history, so fall back to /sessions for deep links.
  // Use history.state (not vue-router's stack) to detect the previous page.
  function listBack(): string | null {
    const back = window.history.state?.back
    const cameFromList =
      typeof back === 'string' && back.startsWith('/sessions') && !back.startsWith('/sessions/')
    return cameFromList ? back : null
  }

  // Neighbours come from the cached list page and the runs the list had open, rebuilt from the
  // list URL's query. No cache, or this session not in that sequence, means no links; the first
  // and last session have one neighbour.
  const nav = computed(() => {
    const back = listBack()
    if (!back) return null
    const q = new URL(back, window.location.origin).searchParams
    const listQuery = sessionsListQuery((k) => q.get(k) ?? undefined)
    const page = queryClient.getQueryData<ListSessionsResponse>(
      listSessionsOptions({ query: listQuery }).queryKey,
    )
    if (!page) return null
    const { sort, order, has, country, q: term, sha256 } = listQuery
    const seq = buildSequence(
      page,
      (q.get('run') ?? '').split(','),
      (first, n) =>
        page.as_of && first.run
          ? queryClient.getQueryData<RunSessionsResponse>(
              listRunSessionsOptions({
                query: {
                  sort,
                  order,
                  has,
                  country,
                  q: term,
                  sha256,
                  as_of: page.as_of,
                  offset: first.run.offset,
                  count: first.run.count,
                  page: n,
                  per_page: SESSIONS_PER_PAGE,
                },
              }).queryKey,
            )?.items
          : undefined,
      SESSIONS_PER_PAGE,
    )
    const i = seq.findIndex((r) => r.id === sessionId.value)
    if (i < 0) return null
    return {
      row: seq[i]!,
      position: i + 1,
      count: seq.length,
      prev: seq[i - 1]?.id,
      next: seq[i + 1]?.id,
    }
  })

  // Previous/Next only change the id on this instance, so nothing tells a screen reader the page
  // changed and focus would sit on a link that now points elsewhere (WCAG 4.1.3, 2.4.3).
  const heading = ref<HTMLElement | null>(null)
  const announcement = ref('')
  watch(sessionId, async () => {
    await nextTick()
    heading.value?.focus({ preventScroll: true })
    announcement.value = nav.value
      ? `Session ${nav.value.position} of ${nav.value.count} on this page`
      : ''
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
          </RouterLink>
          <span v-else class="pager-link disabled" role="link" aria-disabled="true">Previous</span>
          <RouterLink
            v-if="nav.next"
            :to="{ name: 'session-detail', params: { id: nav.next } }"
            replace
            class="pager-link"
          >
            Next
          </RouterLink>
          <span v-else class="pager-link disabled" role="link" aria-disabled="true">Next</span>
        </div>
      </div>
      <span class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</span>
      <p v-if="!session" class="missing" role="alert">Session not found.</p>
      <SessionTerminal v-else :session="session" :row="nav?.row" class="terminal-hero" />
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

  .missing {
    margin: 0;
    color: var(--text-muted);
    font-size: 14px;
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

  /* Same phone edge as LIST_PHONE_MQ in utils/breakpoints.ts. */
  @media (max-width: 759.98px) {
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
