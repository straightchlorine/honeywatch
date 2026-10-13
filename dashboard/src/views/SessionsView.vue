<script setup lang="ts">
  /**
   * Sessions explorer: ranked by interest by default, with outcome/country/sort
   * filters and server-side pagination. Rows expand in place (no navigation).
   * All state (filters, page, expanded row) is URL-based for sharing and back-nav.
   */
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter, type LocationQuery } from 'vue-router'
  import { useQueries, useQuery, keepPreviousData } from '@tanstack/vue-query'
  import type { ListSessionsData } from '@/api/generated/types.gen'
  import {
    listRunSessionsOptions,
    listSessionsOptions,
    statsOutcomesOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import { suspenseAll } from '@/api/queries'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import ChipButton from '@/components/base/ChipButton.vue'
  import Dropdown from '@/components/base/Dropdown.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import SortableTh from '@/components/base/SortableTh.vue'
  import SessionRow from '@/components/sessions/SessionRow.vue'
  import SessionGroupRow from '@/components/sessions/SessionGroupRow.vue'
  import SessionsPhoneList from '@/components/sessions/SessionsPhoneList.vue'
  import OutcomeFilter from '@/components/sessions/OutcomeFilter.vue'
  import PhoneControls from '@/components/sessions/PhoneControls.vue'
  import { ICONS } from '@/components/icons'
  import { fmtNumber } from '@/utils/format'
  import { useCountryOptions } from '@/composables/useCountryOptions'
  import { useIsPhone } from '@/composables/useIsPhone'
  import { setLastViewed, setViewedSpot, takeLastViewed, takeViewedSpot } from '@/utils/lastViewed'
  import { SCORE_TIP, type SessionRow as Row } from '@/utils/sessionStory'
  import { SESSIONS_PER_PAGE, sessionsListQuery } from '@/utils/pagination'

  // Debounce the *fetch*, not the keystroke: the box updates instantly, the
  // URL/query only commits once typing pauses.
  const SEARCH_DEBOUNCE_MS = 250
  // On a phone the list must come back from cache on Back, unchanged: a refetch would shift the
  // restored scroll position under the user.
  const PHONE_STALE_MS = 4 * 60_000
  // Give up looking for the row Back should return to.
  const RETURN_GIVE_UP_MS = 3000
  // Server bounds on `q` (api/src/schemas/sessions.py) - outside [2, 64] the
  // API 422s, so the box never lets a keystroke produce either edge.
  const MIN_QUERY_LEN = 2
  const MAX_QUERY_LEN = 64

  type SortId = NonNullable<NonNullable<ListSessionsData['query']>['sort']>
  const SORTS: { id: SortId; label: string }[] = [
    { id: 'interest', label: 'Most interesting' },
    { id: 'recent', label: 'Most recent' },
    { id: 'duration', label: 'Longest' },
    { id: 'active', label: 'Most active' },
    { id: 'country', label: 'By origin' },
  ]
  // Subtitles must reflect actual sort order (not independent hardcoded values).
  const SORT_SUBTITLE: Record<SortId, string> = {
    interest: 'ranked by how much the attacker did',
    recent: 'newest first',
    duration: 'longest sessions first',
    active: 'most SSH commands issued first',
    country: 'sorted alphabetically by origin',
  }
  // The phone's header has one short line, so the clause is shorter.
  const SORT_SUBTITLE_PHONE: Record<SortId, string> = {
    interest: 'most interesting first',
    recent: 'newest first',
    duration: 'longest first',
    active: 'most commands first',
    country: 'by country, A to Z',
  }
  const SORT_DIR: Record<SortId, 'asc' | 'desc'> = {
    interest: 'desc',
    recent: 'desc',
    duration: 'desc',
    active: 'desc',
    country: 'asc',
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
  // Before the top-level await below: the listener must register on the setup scope.
  const isPhone = useIsPhone()
  // Once the user leaves this list (a row is tapped, or another page is opened) the route is no
  // longer /sessions: reading its query or writing through updateQuery would clobber that route.
  // This view stays mounted through the Suspense exit, so the frozen query also stops a refetch.
  const leaving = (): boolean => route.name !== 'sessions'
  const qry = computed<LocationQuery>((prev) => (leaving() ? (prev ?? route.query) : route.query))

  // Merges over the last *requested* query, not the route's: two same-tick
  // calls would otherwise both spread the stale query and the second
  // replace() clobbers the first.
  let pendingQuery: LocationQuery | null = null
  function updateQuery(patch: Record<string, string | undefined>): void {
    if (leaving()) return
    const next: LocationQuery = { ...(pendingQuery ?? qry.value) }
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
    get: () => (qry.value.has as string | undefined) ?? '',
    set: (v) => updateQuery({ has: v || undefined, page: undefined, open: undefined }),
  })
  const sort = computed<SortId>({
    get: () => (qry.value.sort as SortId | undefined) ?? 'interest',
    set: (v) => {
      updateQuery({
        sort: v === 'interest' ? undefined : v,
        order: undefined,
        page: undefined,
        open: undefined,
      })
    },
  })
  const order = computed<'asc' | 'desc' | undefined>({
    get: () => qry.value.order as 'asc' | 'desc' | undefined,
    set: (v) => {
      updateQuery({
        order: v,
        page: undefined,
        open: undefined,
      })
    },
  })
  const country = computed<string>({
    get: () => (qry.value.country as string | undefined) ?? '',
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
    get: () => (qry.value.q as string | undefined) ?? '',
    set: (v) => updateQuery({ q: v || undefined, page: undefined, open: undefined }),
  })
  // ?sha256= scopes the list to one captured payload. Read-only here: the
  // Payloads cards are the only thing that sets it, and it is validated
  // server-side, so a hand-typed value that is not 64 lowercase hex 422s
  // rather than silently returning the unfiltered 543k list.
  const shaFilter = computed(() => {
    const v = qry.value.sha256
    return typeof v === 'string' && /^[0-9a-f]{64}$/.test(v) ? v : undefined
  })

  // Expanded row persists in URL (?open=sessionId) to restore on back/forward.
  const expandedId = computed<string | null>({
    get: () => (qry.value.open as string | undefined) ?? null,
    set: (v) => updateQuery({ open: v || undefined }),
  })

  // Current page (?page=N) - 1-based, defaults to 1. Changes to filter/sort/
  // country/search reset this to undefined (which defaults to 1 on read).
  const currentPage = computed<number>({
    get: () => {
      const p = qry.value.page as string | undefined
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
  onBeforeUnmount(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })
  // Back, or a typed ?q=, can change the committed term under the box.
  watch(search, (v) => {
    if (v !== searchInput.value) searchInput.value = v
  })

  // Never sent below the API's 2-char floor - the box can hold a shorter
  // in-progress term without ever producing a request for it.
  const searchActive = computed(() => search.value.length >= MIN_QUERY_LEN)

  const phoneStale = isPhone.value ? { staleTime: PHONE_STALE_MS } : {}
  const listQuery = computed(() => sessionsListQuery((k) => qry.value[k]))
  const sessionsQ = useQuery(
    computed(() => ({
      ...listSessionsOptions({ query: listQuery.value }),
      ...phoneStale,
      // Hold the previous page on screen while the next one loads. Without it
      // rows collapses to [] on every page change and the flex-sized table
      // reflows - a blank frame and a layout jump on a page that must fit the
      // viewport. PulseView and CredentialsView already do this.
      placeholderData: keepPreviousData,
    })),
  )

  await suspenseAll(sessionsQ)

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
      if (!sha || !only || isPhone.value) return
      if (!qry.value.open) expandedId.value = only.id
    },
    { immediate: true },
  )

  onMounted(() => {
    const openRow = scrollEl.value?.querySelector('tr.srow[aria-expanded="true"]')
    // scrollIntoView is absent in jsdom (unit tests) - guard the call, not
    // just the element lookup.
    openRow?.scrollIntoView?.({ block: 'center' })
  })

  const rows = computed(() => sessionsQ.data.value?.items ?? [])
  const total = computed(() => sessionsQ.data.value?.meta.total ?? 0)
  const pageCount = computed(() => sessionsQ.data.value?.meta.pages ?? 1)
  // Global, unfiltered ceiling (stable across pagination - every page carries
  // the same true dataset max) - normalizes the displayed per-row interest
  // score to 0-100 in SessionRow.
  const maxInterest = computed(() => sessionsQ.data.value?.max_interest ?? 0)
  const loadFailed = computed(() => sessionsQ.isError.value && !sessionsQ.isFetching.value)

  const subtitle = computed(() => (isPhone.value ? SORT_SUBTITLE_PHONE : SORT_SUBTITLE)[sort.value])

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

  // Says how many sessions sit behind the folded group rows.
  const pageEnd = computed(() => {
    const closed = [...runs.value].filter(([id]) => !isOpen(id))
    const folded = closed.reduce((n, [, run]) => n + run.count, 0)
    const groups = closed.length
    const shown = rows.value.length + [...members.value.values()].flat().length
    const base = `${shown} row${shown === 1 ? '' : 's'} shown`
    return folded
      ? `${base} \u00b7 ${folded} similar sessions folded into ${groups} group${groups === 1 ? '' : 's'}`
      : base
  })

  const canPrevious = computed(() => currentPage.value > 1)
  const canNext = computed(() => currentPage.value < pageCount.value)

  function clearShaFilter(): void {
    updateQuery({ sha256: undefined, page: undefined, open: undefined })
  }

  // A run's sessions sit behind a group row under its first session, keyed by that session's id.
  // Opening one fetches them a page at a time from the list's own snapshot (as_of).
  const runs = computed(() => new Map(rows.value.flatMap((r) => (r.run ? [[r.id, r.run]] : []))))
  // first id -> pages of the run requested so far. ?run= names the open runs (comma-separated
  // first ids; on desktop the one holding the expanded ?open= session), so a reload or Back
  // reopens them, one page each.
  // Coming Back on a phone restores how deep each run was opened.
  const viewed = takeViewedSpot()
  const openRuns = ref(
    new Map<string, number>(
      (typeof qry.value.run === 'string' ? qry.value.run.split(',') : [])
        .filter(Boolean)
        .map((id) => [id, (isPhone.value && viewed?.runs.get(id)) || 1]),
    ),
  )
  const groupKey = (id: string): string => `group-${id}`
  const isOpen = (first: string): boolean => openRuns.value.has(first)
  // The list the open runs were requested against: the rows on screen. While the next list loads,
  // the rows (and the offsets taken from them) stay on the previous result, so the member requests
  // keep that result's filters and snapshot too.
  const shown = ref<{ query: ReturnType<typeof sessionsListQuery>; asOf?: string } | null>(null)
  watch(
    () => [sessionsQ.data.value, sessionsQ.isPlaceholderData.value] as const,
    ([data, placeholder]) => {
      if (data && !placeholder) shown.value = { query: listQuery.value, asOf: data.as_of }
    },
    { immediate: true },
  )
  const runRequests = computed(() => {
    const at = shown.value
    if (!at?.asOf) return []
    const asOf = at.asOf
    const { sort, order, has, country, q, sha256 } = at.query
    return [...openRuns.value].flatMap(([first, pages]) => {
      const run = runs.value.get(first)
      if (!run) return []
      return Array.from({ length: pages }, (_, i) => ({
        first,
        options: listRunSessionsOptions({
          query: {
            sort,
            order,
            has,
            country,
            q,
            sha256,
            as_of: asOf,
            offset: run.offset,
            count: run.count,
            page: i + 1,
            per_page: SESSIONS_PER_PAGE,
          },
        }),
      }))
    })
  })
  const runPages = useQueries({
    queries: computed(() => runRequests.value.map((r) => ({ ...r.options, ...phoneStale }))),
  })
  const members = computed(() => {
    const out = new Map<string, Row[]>()
    runRequests.value.forEach(({ first }, i) => {
      out.set(first, [...(out.get(first) ?? []), ...(runPages.value[i]?.data?.items ?? [])])
    })
    return out
  })
  const runLoading = (first: string): boolean =>
    runRequests.value.some((r, i) => r.first === first && runPages.value[i]?.isFetching)
  const runMore = (first: string): number =>
    (runs.value.get(first)?.count ?? 0) - (members.value.get(first)?.length ?? 0)
  // A run page that failed leaves its rows out, so the group says so and retries that page.
  const runFailed = (first: string): boolean =>
    runRequests.value.some((r, i) => r.first === first && runPages.value[i]?.isError)
  function retryRun(first: string): void {
    runRequests.value.forEach((r, i) => {
      if (r.first === first && runPages.value[i]?.isError) void runPages.value[i]?.refetch()
    })
  }
  function moreLabel(first: string): string {
    const left = runMore(first)
    const next = `Show ${fmtNumber(Math.min(left, SESSIONS_PER_PAGE))} more`
    return left > SESSIONS_PER_PAGE ? `${next} of ${fmtNumber(left)}` : next
  }
  function loadMore(first: string): void {
    openRuns.value = new Map(openRuns.value).set(first, (openRuns.value.get(first) ?? 0) + 1)
  }
  function toggleRun(first: string): void {
    const next = new Map(openRuns.value)
    if (isOpen(first)) {
      next.delete(first)
      // A row left expanded inside a closing run would vanish from under the user.
      if (members.value.get(first)?.some((m) => m.id === expandedId.value)) {
        updateQuery({ open: undefined, run: undefined })
      }
    } else next.set(first, 1)
    openRuns.value = next
    if (isPhone.value) {
      const ids = [...next.keys()].filter((id) => runs.value.has(id))
      updateQuery({ run: ids.join(',') || undefined })
    }
  }

  const rowLink = (id: string): HTMLElement | undefined =>
    [...document.querySelectorAll<HTMLElement>('a.row')].find((a) => a.dataset.id === id)
  function onOpen(id: string): void {
    setLastViewed(id)
    const top = rowLink(id)?.getBoundingClientRect().top
    if (top !== undefined) setViewedSpot({ id, top, runs: openRuns.value })
  }

  // Back from a session (or an old ?open= link) on a phone: focus the row and bring it into view
  // once it exists. Members of an open run render after their queries land, so this watches the
  // data; if the row never shows up, focus falls to the page instead.
  const lastViewed = takeLastViewed()
  let returnTo: string | null = null
  if (isPhone.value) {
    const open = typeof qry.value.open === 'string' ? qry.value.open : null
    returnTo = lastViewed ?? open
  }
  function finishReturn(el: HTMLElement | null): void {
    returnTo = null
    clearTimeout(returnTimer)
    if (qry.value.open) updateQuery({ open: undefined })
    if (!el) {
      if (document.activeElement === document.body) {
        document.getElementById('main')?.focus({ preventScroll: true })
      }
      return
    }
    el.focus({ preventScroll: true })
    const was = viewed && viewed.id === el.dataset.id ? viewed.top : undefined
    if (was !== undefined) window.scrollBy(0, el.getBoundingClientRect().top - was)
    const { top, bottom } = el.getBoundingClientRect()
    if (top < 0 || bottom > window.innerHeight) el.scrollIntoView?.({ block: 'center' })
  }
  function tryReturn(): void {
    if (!returnTo) return
    const el = rowLink(returnTo)
    if (el || runPages.value.every((q) => !q.isFetching)) finishReturn(el ?? null)
  }
  const returnTimer = returnTo ? setTimeout(() => finishReturn(null), RETURN_GIVE_UP_MS) : undefined
  watch([rows, members], () => nextTick(tryReturn), { flush: 'post' })
  onMounted(tryReturn)
  onBeforeUnmount(() => clearTimeout(returnTimer))

  // Treegrid roving tabindex: the last focused row (or group row) is the Tab stop. It falls back
  // to the first row when that id is not visible, so a page change never leaves zero stops.
  const focusedId = ref<string | null>(null)
  const stopId = computed(() => {
    const visible = rows.value.flatMap((r) =>
      runs.value.has(r.id)
        ? [r.id, groupKey(r.id), ...(members.value.get(r.id) ?? []).map((m) => m.id)]
        : [r.id],
    )
    return visible.includes(focusedId.value ?? '') ? focusedId.value : visible[0]
  })

  // PageUp/PageDown move focus to the new page's first row. focusPage is the page we are waiting
  // on: armed only when the page really changes, dropped on error or if the route lands elsewhere,
  // so a later refetch (sort change) cannot steal focus. Compared with the page the response says
  // it is, because the route changes a tick before the query switches keys.
  let focusPage: number | null = null
  const loadedPage = computed(() => sessionsQ.data.value?.meta.page)
  const settled = computed(() => !sessionsQ.isPlaceholderData.value && !sessionsQ.isFetching.value)
  const pageStatus = ref('')
  let announcedPage = loadedPage.value
  watch([loadedPage, settled, sessionsQ.isError], async ([page, ok, err]) => {
    if (err) focusPage = null
    if (!ok || err || page === undefined) return
    if (page !== announcedPage) {
      announcedPage = page
      const n = rows.value.length
      pageStatus.value = `Page ${page} of ${pageCount.value}, ${n} session${n === 1 ? '' : 's'}`
    }
    if (focusPage === null) return
    if (focusPage !== page) {
      if (currentPage.value !== focusPage) focusPage = null
      return
    }
    focusPage = null
    await nextTick()
    scrollEl.value?.querySelector<HTMLElement>(NAV_ROW)?.focus()
  })
  const NAV_ROW = 'tr.srow, tr.sgroup'
  function onGridFocus(e: FocusEvent): void {
    const id = (e.target as HTMLElement).closest<HTMLElement>(NAV_ROW)?.dataset.id
    if (id) focusedId.value = id
  }
  function onGridKey(e: KeyboardEvent): void {
    const tr = e.target as HTMLElement
    if (!tr.matches(NAV_ROW)) return
    const list = [...(tr.parentElement?.querySelectorAll<HTMLElement>(NAV_ROW) ?? [])]
    const i = list.indexOf(tr)
    const to = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: list.length - 1 }[e.key]
    if (to !== undefined) {
      e.preventDefault()
      list[Math.max(0, Math.min(to, list.length - 1))]?.focus()
    } else if (e.key === 'PageDown' || e.key === 'PageUp') {
      const down = e.key === 'PageDown'
      if (sessionsQ.isFetching.value || !(down ? canNext.value : canPrevious.value)) return
      e.preventDefault()
      const from = currentPage.value
      const to = goToPage(from + (down ? 1 : -1))
      if (to === from) return
      focusPage = to
      focusedId.value = null
    }
  }

  // Collapsing a panel above the tapped row moves it (Safari has no scroll anchoring, and the
  // table's own scroller does not anchor either), so the row is pinned to its screen position.
  let pinned: { id: string; top: number } | null = null
  const rowEl = (id: string): HTMLElement | undefined =>
    [...(scrollEl.value?.querySelectorAll<HTMLElement>('tr.srow') ?? [])].find(
      (r) => r.dataset.id === id,
    )
  watch(
    expandedId,
    () => {
      const pin = pinned
      pinned = null
      if (!pin) return
      const now = rowEl(pin.id)?.getBoundingClientRect().top
      if (now === undefined) return
      const dy = now - pin.top
      if (!dy) return
      const sc = scrollEl.value
      if (sc && sc.scrollHeight > sc.clientHeight) sc.scrollTop += dy
      else window.scrollBy(0, dy)
    },
    { flush: 'post' },
  )
  // Reads the requested ?open=, not the route's: a second tap before the first navigation lands
  // would otherwise toggle against stale state and leave the panel open.
  function toggleRow(id: string, run?: string): void {
    const current = (pendingQuery ?? qry.value).open ?? null
    const top = rowEl(id)?.getBoundingClientRect().top
    pinned = top === undefined ? null : { id, top }
    updateQuery(current === id ? { open: undefined, run: undefined } : { open: id, run })
  }
  // Returns the clamped page it navigated to.
  function goToPage(p: number): number {
    const clamped = Math.max(1, Math.min(p, pageCount.value))
    currentPage.value = clamped
    return clamped
  }
  // Empty/NaN input is ignored. Always resync the box so a value that clamps to the current page leaves no stale text.
  function onPageChange(e: Event): void {
    const el = e.target as HTMLInputElement
    const n = parseInt(el.value, 10)
    el.value = String(Number.isNaN(n) ? currentPage.value : goToPage(n))
  }
  // The pager stays focusable while a page loads (aria-disabled, not disabled), so these guard too.
  function prevPage(): void {
    if (canPrevious.value && !sessionsQ.isFetching.value) goToPage(currentPage.value - 1)
  }
  function nextPage(): void {
    if (canNext.value && !sessionsQ.isFetching.value) goToPage(currentPage.value + 1)
  }

  // Header order; 'spacer' is the unlabeled 4th column (see the width rules in the styles).
  const COLUMNS: (
    { key: SortId; label: string; hint: string; right?: boolean } | { key: 'spacer' }
  )[] = [
    {
      key: 'interest',
      label: 'Session',
      hint: `Sort by interest: how much the attacker did. ${SCORE_TIP}`,
    },
    { key: 'active', label: 'Story', hint: 'Sort by activity: SSH commands issued' },
    { key: 'country', label: 'Origin', hint: 'Sort by origin: alphabetically' },
    { key: 'spacer' },
    { key: 'duration', label: 'Duration', hint: 'Sort by duration: longest first', right: true },
    { key: 'recent', label: 'Started', hint: 'Sort by recency: newest first', right: true },
  ]

  const sortOptions = computed(() => SORTS.map((s) => ({ value: s.id, label: s.label })))
  // Three pills share the phone width, so the pill shows a short sort name; the sheet has the full one.
  const SORT_SHORT: Record<SortId, string> = {
    interest: 'Interesting',
    recent: 'Newest',
    duration: 'Longest',
    active: 'Active',
    country: 'Origin',
  }
  const phoneSortOptions = computed(() =>
    SORTS.map((s) => ({
      value: s.id,
      label: s.label,
      short: SORT_SHORT[s.id],
      hint: SORT_SUBTITLE[s.id],
    })),
  )
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
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
            focusable="false"
          >
            <path d="M18 6l-12 12M6 6l12 12" />
          </svg>
        </button>
      </div>

      <PhoneControls
        v-if="isPhone"
        v-model:has="hasValue"
        v-model:sort="sort"
        v-model:country="country"
        :sort-options="phoneSortOptions"
        :country-options="countryOptions"
        :counts="outcomesQ.data.value ?? null"
      />
      <div v-else class="controls-row">
        <OutcomeFilter v-model="hasValue" :counts="outcomesQ.data.value ?? null" />
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

      <!-- Arriving from a Payloads card narrows a 543k list to a handful. Say
           so, and make it removable, or the scope is invisible and permanent. -->
      <ChipButton v-if="shaFilter" :pressed="true" @toggle="clearShaFilter">
        <span aria-hidden="true" class="mono">{{ shaFilter.slice(0, 12) }}</span>
        <span aria-hidden="true" class="chip-x">&times;</span>
        <span class="visually-hidden">
          Showing only sessions that dropped file {{ shaFilter.slice(0, 12) }}. Remove filter.
        </span>
      </ChipButton>
    </div>

    <HwCard class="tbl-card" :class="{ 'has-rows': rows.length > 0, phone: isPhone }">
      <p v-if="loadFailed" class="load-error" role="alert">
        Could not refresh sessions.
        <ChipButton @toggle="sessionsQ.refetch()">Retry</ChipButton>
      </p>
      <EmptyState
        v-if="rows.length === 0 && !loadFailed"
        :title="emptyTitle"
        :hint="emptyHint"
      >
        <ChipButton v-if="searchActive" @toggle="clearSearch">Clear search</ChipButton>
      </EmptyState>
      <SessionsPhoneList
        v-else-if="rows.length > 0 && isPhone"
        :rows="rows"
        :members="members"
        :open-runs="openRuns"
        :sort="sort"
        :max-interest="maxInterest"
        :busy="sessionsQ.isPlaceholderData.value"
        :run-loading="runLoading"
        :more-label="moreLabel"
        @toggle-run="toggleRun"
        @more="loadMore"
        @open="onOpen"
      />
      <div
        v-else-if="rows.length > 0"
        ref="scrollEl"
        class="tbl-scroll"
        :class="{ stale: sessionsQ.isPlaceholderData.value }"
        :aria-busy="sessionsQ.isPlaceholderData.value"
        tabindex="0"
        role="region"
        aria-label="Sessions table"
      >
        <!-- treegrid, not table: rows carry aria-expanded because each one
             discloses a detail panel, and aria-expanded is only valid on a row
             inside a treegrid (axe rule aria-conditional-attr). -->
        <table class="data" role="treegrid" aria-label="Sessions">
          <thead>
            <tr>
              <template v-for="c in COLUMNS" :key="c.key">
                <th v-if="c.key === 'spacer'" aria-hidden="true"></th>
                <SortableTh
                  v-else
                  v-model:sort="sort"
                  v-model:order="order"
                  :sort-key="c.key"
                  :dir="SORT_DIR[c.key]"
                  :hint="c.hint"
                  :class="{ r: c.right }"
                >
                  {{ c.label
                  }}<span v-if="c.key === 'interest'" class="story-key" aria-hidden="true"
                    >interest 0-100</span
                  ><span v-else-if="c.key === 'active'" class="story-key" aria-hidden="true"
                    >commands &middot; files &middot; relays</span
                  >
                </SortableTh>
              </template>
            </tr>
          </thead>
          <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- delegated treegrid keys; the focusable rows are the targets -->
          <tbody @focusin="onGridFocus" @keydown="onGridKey">
            <template v-for="row in rows" :key="row.id">
              <SessionRow
                :row="row"
                :expanded="expandedId === row.id"
                :max-interest="maxInterest"
                :tabbable="row.id === stopId"
                @toggle="toggleRow(row.id)"
              />
              <template v-if="row.run">
                <SessionGroupRow
                  :data-id="groupKey(row.id)"
                  :row="row"
                  :run="row.run"
                  :open="isOpen(row.id)"
                  :tabbable="groupKey(row.id) === stopId"
                  @toggle="toggleRun(row.id)"
                />
                <template v-if="isOpen(row.id)">
                  <SessionRow
                    v-for="m in members.get(row.id) ?? []"
                    :key="m.id"
                    :row="m"
                    :expanded="expandedId === m.id"
                    :max-interest="maxInterest"
                    :tabbable="m.id === stopId"
                    nested
                    @toggle="toggleRow(m.id, row.id)"
                  />
                  <tr v-if="runLoading(row.id) || runMore(row.id) > 0" class="run-more">
                    <td colspan="6">
                      <span v-if="runLoading(row.id)" role="status">Loading&hellip;</span>
                      <template v-else-if="runFailed(row.id)">
                        <span role="alert">Could not load these sessions.</span>
                        <ChipButton @toggle="retryRun(row.id)">Retry</ChipButton>
                      </template>
                      <ChipButton v-else @toggle="loadMore(row.id)">
                        {{ moreLabel(row.id) }}
                      </ChipButton>
                    </td>
                  </tr>
                </template>
              </template>
            </template>
          </tbody>
        </table>
        <p class="page-end">
          {{ pageEnd }}
        </p>
      </div>
    </HwCard>

    <span class="visually-hidden" role="status" aria-live="polite">{{ pageStatus }}</span>

    <div class="foot-line">
      <span>
        <b>{{ SESSIONS_PER_PAGE }}</b> per page &middot; {{ fmtNumber(total) }}
        {{ scopeClause ?? 'sessions'
        }}<span v-if="!scopeClause" class="hint-tail"> &middot; select a row to expand it</span>
      </span>
      <div class="pagination">
        <button
          type="button"
          class="pg-btn"
          :aria-disabled="!canPrevious || sessionsQ.isFetching.value"
          @click="prevPage"
          aria-label="Previous page"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
            <path :d="ICONS['chevron-left']" fill="currentColor" />
          </svg>
          <span v-if="isPhone" aria-hidden="true">Prev</span>
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
            @change="onPageChange"
            aria-label="Current page number"
          />
          <span class="page-label">of {{ fmtNumber(pageCount) }}</span>
        </div>
        <button
          type="button"
          class="pg-btn"
          :aria-disabled="!canNext || sessionsQ.isFetching.value"
          @click="nextPage"
          aria-label="Next page"
        >
          <span v-if="isPhone" aria-hidden="true">Next</span>
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </button>
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
  /* Visible key for the Story pills; hidden on phones, where the pills keep their title attrs. */
  .story-key {
    margin-left: 8px;
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    color: var(--text-dim);
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
    color: var(--text-dim);
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
  .pg-btn:hover:not([aria-disabled='true']) {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  .pg-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .pg-btn[aria-disabled='true'] {
    color: color-mix(in srgb, var(--text-dim) 55%, transparent);
    cursor: default;
  }

  .tbl-card {
    flex: 1;
    min-height: 0;
    /* Side inset so rows and the scrollbar do not sit on the card border; the
       first/last columns give back the same 8px so the text does not move. */
    padding: 0 8px;
    overflow: hidden;
    position: relative;
  }
  .tbl-scroll {
    overflow-y: auto;
    height: 100%;
    transition: opacity var(--motion-fast);
    scrollbar-width: thin;
    scrollbar-color: color-mix(in srgb, var(--text-dim) 55%, transparent) transparent;
  }
  .tbl-card.phone {
    padding: 0;
  }
  .tbl-card.phone::after {
    display: none;
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

  /* Lines up with the nested rows' chevrons. */
  table.data tr.run-more td {
    padding: 6px 8px 8px 50px;
    color: var(--text-dim);
    font-size: 12px;
  }
  .page-end {
    margin: 0;
    padding: 14px 10px 16px;
    color: var(--text-dim);
    font-size: 12.5px;
    text-wrap: balance;
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
    /* Session / Story / Origin / spacer / Duration / Started column widths.
       Column 4 (spacer) has no width so fixed layout gives it all leftover space.
       border-box: widths are the column's actual width, padding included. */
    box-sizing: border-box;
  }
  table.data th.r {
    text-align: right;
  }
  table.data th:nth-child(1) {
    width: 290px;
    padding-left: 8px;
  }
  table.data th:nth-child(2) {
    width: 400px;
  }
  table.data th:nth-child(3) {
    width: 260px;
  }
  table.data th:nth-child(5) {
    width: 130px;
  }
  table.data th:nth-child(6) {
    width: 150px;
    padding-right: 14px;
  }
  table.data :deep(td) {
    padding: 9px 10px;
    border-bottom: 1px solid var(--grid-line);
    vertical-align: middle;
  }
  table.data :deep(tr[tabindex]) {
    cursor: pointer;
  }
  table.data :deep(tr[tabindex]:focus) {
    outline: none;
  }
  table.data :deep(tr[tabindex]:focus-visible) {
    outline: 2px solid var(--accent-hot);
    outline-offset: -2px;
  }
  table.data :deep(td.r) {
    text-align: right;
  }
  table.data :deep(.num) {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  /* Narrow-desktop band (760-1299px): the desktop table is 1230px of fixed columns and the card is
     the viewport minus 46px, so it only fits from 1292px up; below that Origin and Duration/Started
     scrolled off (the compact rules stop at 1299.98px, the first width where the full table fits).
     Sizes below were set for 760-899px, the tightest case; 900-1179px keeps them, 1180px+ gets
     roomier columns. What yields first, in order: the header
     key lines (the tooltip still says what the column is), the city (flag + country name the
     origin; the full place stays in the cell's title), the group row's "Hide" word (the chevron
     says it), the right-aligned headers' left padding, chip padding. Story chips, ids and
     times keep full size: they are what a reader scans. Fixed columns sum to 580px; Origin
     takes the rest (134px at the 714px card minimum, 274px at 900px). */
  @media (min-width: 760px) and (max-width: 1299.98px) {
    table.data th:nth-child(1) {
      width: 208px;
    }
    table.data th:nth-child(2) {
      width: 160px;
    }
    /* Origin has no width of its own here: with the spacer at 0 it takes whatever is left. */
    table.data th:nth-child(3) {
      width: auto;
    }
    table.data th:nth-child(4) {
      width: 0;
      padding: 0;
    }
    /* 8px keeps a sorted header's chevron off the neighbouring label. */
    table.data th:nth-child(5) {
      width: 104px;
      padding-left: 8px;
    }
    table.data th:nth-child(6) {
      width: 108px;
      padding-left: 8px;
    }
    .story-key {
      display: none;
    }
  }
  /* 1180-1299px: room for the full-width Story column again, still without the 1230px floor. */
  @media (min-width: 1180px) and (max-width: 1299.98px) {
    table.data th:nth-child(1) {
      width: 250px;
    }
    table.data th:nth-child(2) {
      width: 300px;
    }
    table.data th:nth-child(5) {
      width: 110px;
    }
    table.data th:nth-child(6) {
      width: 160px;
    }
    .story-key {
      display: inline;
    }
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
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--text-muted);
    font: 550 12.5px var(--font-mono);
    font-variant-numeric: tabular-nums;
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

  .tbl-scroll.stale {
    opacity: 0.7;
  }
  .load-error {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0;
    padding: 8px 16px;
    color: var(--text-dim);
    font-size: 12.5px;
  }

  /* Touch: match the 44px pager buttons and keep inputs at 16px so iOS does
     not zoom on focus. */
  @media (pointer: coarse) {
    .foot-line .page-input {
      min-height: var(--control-h);
    }
    .search-clear {
      width: 32px;
      height: 32px;
      margin: -7px -6px -7px 0;
    }
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

  @media (max-width: 759.98px) {
    .search-box input,
    .foot-line .page-input {
      font-size: 16px;
    }
    .filters {
      flex-direction: column;
      align-items: stretch;
    }
    .search-box {
      width: 100%;
    }
    .page-end {
      padding: 4px 8px 12px;
      color: var(--text-muted);
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
    .search-box {
      border-radius: 999px;
      padding-left: 16px;
    }
    .foot-line > span {
      text-align: center;
    }
    .foot-line > span b {
      color: var(--text-muted);
      font-weight: 600;
    }
    .foot-line .pagination {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 8px;
    }
    .foot-line .page-control {
      justify-content: center;
    }
    .foot-line .page-input {
      width: 56px;
    }
    .pg-btn {
      width: auto;
      min-width: var(--control-h);
      gap: 6px;
      padding: 0 14px;
      font: 550 13px var(--font-sans);
    }
  }
</style>
