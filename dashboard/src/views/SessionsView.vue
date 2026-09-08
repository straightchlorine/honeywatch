<script setup lang="ts">
  /**
   * Sessions explorer: ranked by interest by default, with outcome/country/sort
   * filters and server-side pagination. Rows expand in place (no navigation).
   * All state (filters, page, expanded row) is URL-based for sharing and back-nav.
   */
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { useRoute, useRouter, type LocationQuery } from 'vue-router'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import {
    listSessionsOptions,
    statsOutcomesOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import ChipButton from '@/components/base/ChipButton.vue'
  import Dropdown from '@/components/base/Dropdown.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import SessionRow from '@/components/sessions/SessionRow.vue'
  import OutcomeFilter from '@/components/sessions/OutcomeFilter.vue'
  import { ICONS } from '@/components/icons'
  import { fmtNumber } from '@/utils/format'
  import { useCountryOptions } from '@/composables/useCountryOptions'

  const PER_PAGE = 40
  // Debounce the *fetch*, not the keystroke: the box updates instantly, the
  // URL/query only commits once typing pauses.
  const SEARCH_DEBOUNCE_MS = 250
  // Server bounds on `q` (api/src/schemas/sessions.py) - outside [2, 64] the
  // API 422s, so the box never lets a keystroke produce either edge.
  const MIN_QUERY_LEN = 2
  const MAX_QUERY_LEN = 64

  type SortId = 'interest' | 'recent' | 'duration'
  const SORTS: { id: SortId; label: string }[] = [
    { id: 'interest', label: 'Most interesting' },
    { id: 'recent', label: 'Most recent' },
    { id: 'duration', label: 'Longest' },
  ]
  // Subtitles must reflect actual sort order (not independent hardcoded values).
  const SORT_SUBTITLE: Record<SortId, string> = {
    interest: 'ranked by how much the attacker did',
    recent: 'newest first',
    duration: 'longest sessions first',
  }
  // Short, lowercase clauses for the footer's "what the total is of" - keyed
  // by the OutcomeFilter has= token (see OutcomeFilter.vue's MAIN_ROWS/NONE_ROW).
  const OUTCOME_CLAUSE: Record<string, string> = {
    success: 'got control',
    commands: 'ran commands',
    tcpip: 'tried to relay',
    downloads: 'dropped a file',
    none: 'did nothing at all',
  }

  // Every filter, the sort, the expanded row and the page live in the URL, so a
  // view is shareable and survives refresh and back.
  const route = useRoute()
  const router = useRouter()

  // Merges over the last *requested* query, not route.query: two same-tick
  // calls would otherwise both spread the stale route.query and the second
  // replace() clobbers the first.
  let pendingQuery: LocationQuery | null = null
  function updateQuery(patch: Record<string, string | undefined>): void {
    const next: LocationQuery = { ...(pendingQuery ?? route.query) }
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined) delete next[k]
      else next[k] = v
    }
    pendingQuery = next
    void router.replace({ path: route.path, query: next }).finally(() => {
      pendingQuery = null
    })
  }

  // URL key `has` holds the API's comma-list verbatim ('commands,success', or
  // the mutually-exclusive 'none').
  const hasValue = computed<string>({
    get: () => (route.query.has as string | undefined) ?? '',
    set: (v) => updateQuery({ has: v || undefined, page: undefined, open: undefined }),
  })
  const sort = computed<SortId>({
    get: () => (route.query.sort as SortId | undefined) ?? 'interest',
    set: (v) => {
      updateQuery({
        sort: v === 'interest' ? undefined : v,
        page: undefined,
        open: undefined,
      })
    },
  })
  const country = computed<string>({
    get: () => (route.query.country as string | undefined) ?? '',
    set: (v) => {
      updateQuery({
        country: v || undefined,
        page: undefined,
        open: undefined,
      })
    },
  })
  // Committed search term (URL state, ?q=) - same reset behavior as every
  // other filter.
  const search = computed<string>({
    get: () => (route.query.q as string | undefined) ?? '',
    set: (v) => updateQuery({ q: v || undefined, page: undefined, open: undefined }),
  })
  // ?sha256= scopes the list to one captured payload. Read-only here: the
  // Payloads cards are the only thing that sets it, and it is validated
  // server-side, so a hand-typed value that is not 64 lowercase hex 422s
  // rather than silently returning the unfiltered 543k list.
  const shaFilter = computed(() => {
    const v = route.query.sha256
    return typeof v === 'string' && /^[0-9a-f]{64}$/.test(v) ? v : undefined
  })

  // Expanded row persists in URL (?open=sessionId) to restore on back/forward.
  const expandedId = computed<string | null>({
    get: () => (route.query.open as string | undefined) ?? null,
    set: (v) => updateQuery({ open: v || undefined }),
  })

  // Current page (?page=N) - 1-based, defaults to 1. Changes to filter/sort/
  // country/search reset this to undefined (which defaults to 1 on read).
  const currentPage = computed<number>({
    get: () => {
      const p = route.query.page as string | undefined
      return p ? Math.max(1, parseInt(p, 10)) : 1
    },
    set: (v) => updateQuery({ page: v > 1 ? String(v) : undefined }),
  })

  const countryOptions = useCountryOptions('All countries')

  // Outcome counts for the popover - scoped to the current country so the
  // numbers in the panel agree with what the country dropdown would return.
  // Not part of the page's blocking suspense (below): the panel's own counts
  // can arrive after first paint without holding up the table.
  const outcomesQ = useQuery(
    computed(() => ({
      ...statsOutcomesOptions({ query: { country: country.value || undefined } }),
    })),
  )

  // The search box's live value. Sanitized on every keystroke (lowercase hex
  // only, per the API's contract) so a stray character can never reach the
  // API as an invalid `q` and 422. Committed to `search` (and so the URL and
  // the fetch) only after SEARCH_DEBOUNCE_MS of no typing.
  const searchInput = ref(search.value)
  let searchTimer: ReturnType<typeof setTimeout> | undefined
  function onSearchInput(e: Event): void {
    const clean = (e.target as HTMLInputElement).value
      .toLowerCase()
      .replace(/[^0-9a-f]/g, '')
      .slice(0, MAX_QUERY_LEN)
    searchInput.value = clean
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      if (clean !== search.value) search.value = clean
    }, SEARCH_DEBOUNCE_MS)
  }
  function clearSearch(): void {
    if (searchTimer) clearTimeout(searchTimer)
    searchInput.value = ''
    if (search.value) search.value = ''
  }
  onUnmounted(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })

  // Never sent below the API's 2-char floor - the box can hold a shorter
  // in-progress term without ever producing a request for it.
  const searchActive = computed(() => search.value.length >= MIN_QUERY_LEN)
  const qParam = computed(() => (searchActive.value ? search.value : undefined))

  const sessionsQ = useQuery(
    computed(() => ({
      ...listSessionsOptions({
        query: {
          page: currentPage.value,
          per_page: PER_PAGE,
          sort: sort.value,
          has: hasValue.value || undefined,
          country: country.value || undefined,
          q: qParam.value,
          sha256: shaFilter.value,
        },
      }),
      // Hold the previous page on screen while the next one loads. Without it
      // rows collapses to [] on every page change and the flex-sized table
      // reflows - a blank frame and a layout jump on a page that must fit the
      // viewport. PulseView and CredentialsView already do this.
      placeholderData: keepPreviousData,
    })),
  )

  await sessionsQ.suspense()
  if (sessionsQ.error.value) throw sessionsQ.error.value

  // The onMounted below is written after the top-level await above; script
  // setup's compiler preserves the instance context across await
  // expressions, so the hook still attaches correctly. It only fires once
  // the initial render is committed to the DOM, well after this line runs.
  const scrollEl = ref<HTMLElement | null>(null)

  // Auto-open only when EXACTLY one matching session exists; picking a "best"
  // row from many would be a guess, and the list is the right answer.
  watch(
    [shaFilter, () => sessionsQ.data.value?.items],
    ([sha, items]) => {
      const only = items?.length === 1 ? items[0] : undefined
      if (!sha || !only) return
      if (!route.query.open) expandedId.value = only.id
    },
    { immediate: true },
  )

  onMounted(() => {
    const openRow = scrollEl.value?.querySelector('tr[aria-expanded="true"]')
    // scrollIntoView is absent in jsdom (unit tests) - guard the call, not
    // just the element lookup.
    openRow?.scrollIntoView?.({ block: 'nearest' })
  })

  const rows = computed(() => sessionsQ.data.value?.items ?? [])
  const total = computed(() => sessionsQ.data.value?.meta.total ?? 0)
  const pageCount = computed(() => sessionsQ.data.value?.meta.pages ?? 1)
  // Global, unfiltered ceiling (stable across pagination - every page carries
  // the same true dataset max) - normalizes the displayed per-row interest
  // score to 0-100 in SessionRow.
  const maxInterest = computed(() => sessionsQ.data.value?.max_interest ?? 0)

  const subtitle = computed(() => SORT_SUBTITLE[sort.value])

  // What the footer's total is a count *of*, when some scope narrows it below
  // "every session" - null means the plain "sessions" wording applies.
  const scopeClause = computed<string | null>(() => {
    if (searchActive.value) return `matching "${search.value}"`
    const parts: string[] = []
    const outcomeLabels = hasValue.value
      ? hasValue.value
          .split(',')
          .map((t) => OUTCOME_CLAUSE[t])
          .filter((l): l is string => Boolean(l))
      : []
    if (outcomeLabels.length) parts.push(outcomeLabels.join(' and '))
    if (country.value) {
      const label = countryOptions.value.find((o) => o.value === country.value)?.label
      if (label) parts.push(`from ${label}`)
    }
    return parts.length ? parts.join(' ') : null
  })

  const emptyTitle = computed(() =>
    searchActive.value ? `No sessions match "${search.value}"` : 'No sessions match these filters',
  )
  const emptyHint = computed(() =>
    searchActive.value
      ? 'Search matches the start of a session id.'
      : 'Try a different outcome, country, or search.',
  )

  // Only when a country is actually set: option[0] is the '' / 'All countries'
  // entry, and matching it would show a pressed chip offering to clear a
  // filter that isn't applied.
  const countryChip = computed(() =>
    country.value ? countryOptions.value.find((o) => o.value === country.value) : undefined,
  )

  const canPrevious = computed(() => currentPage.value > 1)
  const canNext = computed(() => currentPage.value < pageCount.value)

  function clearShaFilter(): void {
    updateQuery({ sha256: undefined, page: undefined, open: undefined })
  }

  function toggleRow(id: string): void {
    expandedId.value = expandedId.value === id ? null : id
  }
  function goToPage(p: number): void {
    const clamped = Math.max(1, Math.min(p, pageCount.value))
    currentPage.value = clamped
  }
  function prevPage(): void {
    if (canPrevious.value) goToPage(currentPage.value - 1)
  }
  function nextPage(): void {
    if (canNext.value) goToPage(currentPage.value + 1)
  }

  const sortOptions = computed(() => SORTS.map((s) => ({ value: s.id, label: s.label })))
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="sessions" />
    </template>

    <div class="page-head">
      <h1>Sessions</h1>
      <span class="sub">{{ fmtNumber(total) }} recorded &middot; {{ subtitle }}</span>
    </div>

    <div class="filters" role="group" aria-label="Session filters">
      <div class="search-box">
        <svg
          class="search-icon"
          :class="{ active: searchInput.length > 0 }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          aria-hidden="true"
          focusable="false"
        >
          <circle cx="10" cy="10" r="6" />
          <path d="M14 14l6 6" />
        </svg>
        <input
          id="session-search"
          :value="searchInput"
          type="text"
          autocomplete="off"
          spellcheck="false"
          placeholder="find a session id"
          aria-label="Search sessions by id"
          @input="onSearchInput"
        />
        <span v-if="searchActive" class="match-count" role="status">
          {{ fmtNumber(total) }} match{{ total === 1 ? '' : 'es' }}
        </span>
        <button
          v-if="searchInput"
          type="button"
          class="search-clear"
          aria-label="Clear search"
          @click="clearSearch"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true" focusable="false">
            <path d="M18 6l-12 12M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="controls-row">
        <OutcomeFilter
          v-model="hasValue"
          :counts="outcomesQ.data.value ?? null"
        />
        <div class="right">
          <span class="country-control">
            <Dropdown
              button-id="country-dd"
              label-id="country-label"
              :model-value="country"
              :options="countryOptions"
              @update:model-value="country = $event"
            />
            <span id="country-label" class="visually-hidden">Country filter</span>
          </span>
          <span class="sort-control">
            <Dropdown
              button-id="sort-dd"
              label-id="sort-label"
              :model-value="sort"
              :options="sortOptions"
              @update:model-value="sort = $event as SortId"
            />
            <span id="sort-label" class="visually-hidden">Sort</span>
          </span>
        </div>
      </div>

      <!-- Mobile-only (see media query): the country dropdown above is
           dropped at that width, so a shared ?country= link still needs a
           visible, removable affordance - display:none hides this on desktop,
           where the dropdown itself already shows the active country. -->
      <ChipButton v-if="countryChip" class="country-chip" :pressed="true" @toggle="country = ''">
        <span aria-hidden="true">{{ countryChip.icon }}</span>
        <span aria-hidden="true">{{ countryChip.label }}</span>
        <span aria-hidden="true" class="chip-x">&times;</span>
        <span class="visually-hidden">Remove country filter: {{ countryChip.label }}</span>
      </ChipButton>

      <!-- Arriving from a Payloads card narrows a 543k list to a handful. Say
           so, and make it removable, or the scope is invisible and permanent. -->
      <ChipButton v-if="shaFilter" class="sha-chip" :pressed="true" @toggle="clearShaFilter">
        <span aria-hidden="true" class="mono">{{ shaFilter.slice(0, 12) }}</span>
        <span aria-hidden="true" class="chip-x">&times;</span>
        <span class="visually-hidden">
          Showing only sessions that dropped file {{ shaFilter.slice(0, 12) }}. Remove filter.
        </span>
      </ChipButton>
    </div>

    <HwCard class="tbl-card" :class="{ 'has-rows': rows.length > 0 }">
      <EmptyState v-if="rows.length === 0" :title="emptyTitle" :hint="emptyHint">
        <ChipButton v-if="searchActive" @toggle="clearSearch">Clear search</ChipButton>
      </EmptyState>
      <div v-else ref="scrollEl" class="tbl-scroll" tabindex="0" role="region" aria-label="Sessions table">
        <!-- treegrid, not table: rows carry aria-expanded because each one
             discloses a detail panel, and aria-expanded is only valid on a row
             inside a treegrid (axe rule aria-conditional-attr). -->
        <table class="data" role="treegrid" aria-label="Sessions">
          <thead>
            <tr>
              <th>Session</th>
              <th>Story</th>
              <th>Origin</th>
              <th></th>
              <th class="r">Duration</th>
              <th class="r">Started</th>
            </tr>
          </thead>
          <tbody>
            <SessionRow
              v-for="row in rows"
              :key="row.id"
              :row="row"
              :expanded="expandedId === row.id"
              :max-interest="maxInterest"
              @toggle="toggleRow(row.id)"
            />
          </tbody>
        </table>
      </div>
    </HwCard>

    <div class="foot-line">
      <span>
        <b>{{ PER_PAGE }}</b> per page &middot; {{ fmtNumber(total) }} {{ scopeClause ?? 'sessions'
        }}<span v-if="!scopeClause" class="hint-tail">
          &middot; rows expand in place - the list never navigates away</span
        >
      </span>
      <div class="pagination">
        <button
          type="button"
          class="pg-btn"
          :disabled="!canPrevious || sessionsQ.isFetching.value"
          @click="prevPage"
          aria-label="Previous page"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
            <path :d="ICONS['chevron-left']" fill="currentColor" />
          </svg>
        </button>
        <div class="page-control">
          <span class="page-label">Page</span>
          <input
            id="page-input"
            type="number"
            class="page-input"
            :value="currentPage"
            :min="1"
            :max="pageCount"
            @change="goToPage(parseInt(($event.target as HTMLInputElement).value, 10))"
            @blur="goToPage(parseInt(($event.target as HTMLInputElement).value, 10))"
            aria-label="Current page number"
          />
          <span class="page-label">of {{ fmtNumber(pageCount) }}</span>
        </div>
        <button
          type="button"
          class="pg-btn"
          :disabled="!canNext || sessionsQ.isFetching.value"
          @click="nextPage"
          aria-label="Next page"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
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

  .filters {
    display: flex;
    gap: 8px;
    align-items: center;
    flex: none;
    flex-wrap: wrap;
  }

  .controls-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }

  /* Search box: its own bordered control (not the shared .chip pill) so it
     can hold the icon, the live match count and the clear button together. */
  .search-box {
    width: 280px;
    flex: none;
    box-sizing: border-box;
    min-height: var(--control-h);
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    padding: 6px 10px 6px 12px;
    transition: all var(--motion-fast);
  }
  .search-box:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-glow);
  }
  .search-icon {
    flex: 0 0 auto;
    width: 14px;
    height: 14px;
    color: color-mix(in srgb, var(--text-dim) 55%, transparent);
  }
  .search-icon.active {
    color: var(--accent);
  }
  .search-box input {
    flex: 1 1 auto;
    min-width: 0;
    border: none;
    background: transparent;
    outline: none;
    color: var(--text);
    font-family: var(--font-mono);
    font-size: 12.5px;
    font-weight: 550;
  }
  .search-box input::placeholder {
    color: color-mix(in srgb, var(--text-dim) 55%, transparent);
    font-family: var(--font-sans);
  }
  .match-count {
    flex: 0 0 auto;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-weight: 550;
    white-space: nowrap;
  }
  .search-clear {
    flex: 0 0 auto;
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .search-clear:hover {
    color: var(--text);
    background: var(--surface-hover);
  }
  .search-clear:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .search-clear svg {
    width: 12px;
    height: 12px;
  }

  .chip-x {
    font-size: 13px;
    line-height: 1;
  }
  .filters .country-chip {
    display: none;
  }

  .right {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }

  .pg-btn {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h);
    height: var(--control-h);
    box-sizing: border-box;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--motion-fast);
  }
  .pg-btn:hover:not(:disabled) {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  .pg-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .pg-btn:disabled {
    color: color-mix(in srgb, var(--text-dim) 55%, transparent);
    cursor: default;
  }

  .tbl-card {
    flex: 1;
    min-height: 0;
    padding: 0;
    overflow: hidden;
    position: relative;
  }
  .tbl-scroll {
    overflow-y: auto;
    height: 100%;
    scrollbar-width: thin;
    scrollbar-color: color-mix(in srgb, var(--text-dim) 55%, transparent) transparent;
  }
  .tbl-scroll:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  /* Bottom fade: a real affordance that the card scrolls, not just clips.
     Only when rows are actually rendered - the empty state has nothing to
     scroll, and the fade shouldn't sit over its centered message. */
  .tbl-card.has-rows::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 46px;
    background: linear-gradient(to top, var(--surface), transparent);
    pointer-events: none;
  }

  table.data {
    width: 100%;
    /* Fixed layout: column widths come only from the widths below, never from
       cell content - keeps the expanded row's wide transcript preview
       (colspan=6) from shifting every other row's column boundaries. */
    table-layout: fixed;
    border-collapse: collapse;
    font-size: 13px;
  }
  table.data th {
    text-align: left;
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 8px 10px;
    border-bottom: 1px solid var(--border-strong);
    position: sticky;
    top: 0;
    background: var(--surface);
    z-index: 2;
  }
  table.data th.r {
    text-align: right;
  }
  /* Session / Story / Origin / spacer / Duration / Started columns (290px 340px 320px minmax(0,1fr) 130px 150px).
     4th column carries no width so fixed layout hands it all leftover space. */
  /* border-box: widths below are the column's actual width, padding included. */
  table.data th {
    box-sizing: border-box;
  }
  table.data th:nth-child(1) {
    width: 290px;
    padding-left: 16px;
  }
  table.data th:nth-child(2) {
    width: 340px;
  }
  table.data th:nth-child(3) {
    width: 320px;
  }
  table.data th:nth-child(5) {
    width: 130px;
  }
  table.data th:nth-child(6) {
    width: 150px;
    padding-right: 22px;
  }
  table.data :deep(td) {
    padding: 9px 10px;
    border-bottom: 1px solid var(--grid-line);
    vertical-align: middle;
  }
  table.data :deep(td.r) {
    text-align: right;
  }
  table.data :deep(.num) {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  .foot-line {
    flex: none;
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text-dim);
    font-size: 12.5px;
  }
  .foot-line .pagination {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .foot-line .page-control {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .foot-line .page-label {
    font-size: 12.5px;
    color: var(--text-dim);
  }
  .foot-line .page-input {
    width: 48px;
    padding: 4px 6px;
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    font: 550 12.5px var(--font-sans);
    text-align: center;
  }
  .foot-line .page-input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .foot-line .page-input::-webkit-outer-spin-button,
  .foot-line .page-input::-webkit-inner-spin-button {
    appearance: none;
    margin: 0;
  }
  .foot-line .page-input[type='number'] {
    appearance: textfield;
  }

  @media (max-width: 900px) {
    /* Baseline-aligned on one line, the count and subtitle wrap around the
       heading and read as a broken sentence; give each its own line. */
    .page-head {
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
    }
  }

  @media (max-width: 760px) {
    .filters {
      flex-direction: column;
      align-items: stretch;
    }
    .search-box {
      width: 100%;
    }
    .controls-row {
      flex-wrap: wrap;
    }
    /* Outcome + sort share one row, evenly split; the country dropdown is
       dropped entirely (three controls don't fit) in favor of the removable
       chip above, when a country is actually set. */
    .controls-row :deep(.outcome-filter) {
      flex: 1;
    }
    .controls-row :deep(.of-trigger) {
      width: 100%;
      justify-content: space-between;
    }
    .filters .country-chip {
      display: inline-flex;
      align-self: flex-start;
    }
    .right {
      flex: 1;
      margin-left: 0;
    }
    .country-control {
      display: none;
    }
    .sort-control {
      flex: 1;
      display: flex;
    }
    .sort-control :deep(.dropdown) {
      flex: 1;
    }
    .sort-control :deep(.dd-button) {
      width: 100%;
      min-width: 0;
      justify-content: space-between;
    }

    /* Both remaining columns must drop their desktop px widths (340px alone
       would overflow a phone screen) - Session flexes, Story sizes to its badges. */
    /* Not `auto` for both: under table-layout fixed that splits 50/50 and the
       badges wrap to a second line, growing every row. Session must also fit
       the copy button, which `@media (hover: none)` pins visible on touch -
       without that allowance it overflowed the cell onto the badges. Icon
       badges are short enough that Story can give up the width. */
    table.data th:nth-child(1) {
      width: 56%;
    }
    table.data th:nth-child(2) {
      width: 44%;
    }
    table.data th:nth-child(n + 3),
    table.data :deep(td:nth-child(n + 3)) {
      display: none;
    }

    .foot-line {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;
    }
    .foot-line .hint-tail {
      display: none;
    }
    .foot-line .pagination {
      margin-left: 0;
    }
  }
</style>
