<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import {
    statsCountriesOptions,
    statsAsnsOptions,
    statsTopCredentialsOptions,
  } from '@/api/queries'
  import Card from '@/components/base/Card.vue'
  import Stat from '@/components/base/Stat.vue'
  import BarList from '@/components/base/BarList.vue'
  import PageHeader from '@/components/base/PageHeader.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import { buildCredentialFieldRows, fmtSuccessRate } from '@/utils/credentials'
  import {
    buildAsnRows,
    buildCountryLeaderboardRows,
    countryCodeOf,
    countryDisplayName,
    COUNTRY_SORTS,
    UNKNOWN_CODE,
    type CountrySort,
  } from '@/utils/countries'
  import { fmtNumber } from '@/utils/format'
  import { isAlpha2 } from '@/composables/useCountryFilter'
  import { ICONS } from '@/components/icons'

  // The country leaderboard is the heaviest aggregate in the app (sessions x
  // geo x auth_attempts, grouped). It barely moves minute-to-minute and is
  // served with a 30s Cache-Control, so a slower poll never fights the cache --
  // mirrors the Credentials all-time aggregates.
  const POLL_MS = 30_000

  const route = useRoute()
  const router = useRouter()

  // Selection + sort live in the URL so a country view is shareable/reloadable.
  // Read country directly (not useCountryFilter, which is strict alpha-2) so the
  // '??' Unknown-bucket sentinel survives -- only this view drills into it. The
  // alpha-2 check reuses isAlpha2 so the validation regex lives in one place.
  const country = computed<string>(() => {
    const c = route.query.country
    if (typeof c !== 'string') return ''
    if (c === UNKNOWN_CODE) return UNKNOWN_CODE
    return isAlpha2(c) ? c.toUpperCase() : ''
  })
  const SORT_IDS = COUNTRY_SORTS.map((s) => s.id)
  const sort = computed<CountrySort>(() => {
    const s = route.query.sort
    return typeof s === 'string' && (SORT_IDS as string[]).includes(s)
      ? (s as CountrySort)
      : 'sessions'
  })

  const countriesQ = useQuery(
    computed(() => ({
      ...statsCountriesOptions({ query: { sort: sort.value, top_n: 100 } }),
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  await countriesQ.suspense()

  const rows = computed(() => countriesQ.data.value?.countries ?? [])
  const totalCountries = computed(() => countriesQ.data.value?.total_countries ?? 0)
  const geoPctLabel = computed(() =>
    fmtSuccessRate(countriesQ.data.value?.geo_resolved_pct ?? null),
  )
  const leaderRows = computed(() => buildCountryLeaderboardRows(rows.value, sort.value))

  // The leaderboard's ranking axis, surfaced to assistive tech: the list is
  // ordered by it, but that order is invisible to a screen reader otherwise.
  const activeSortLabel = computed(
    () => COUNTRY_SORTS.find((s) => s.id === sort.value)?.label ?? 'Sessions',
  )
  const leaderboardLabel = computed(() => `Country leaderboard, ranked by ${activeSortLabel.value}`)

  // Auto-select the #1 selectable country when the URL names none, so the detail
  // panel (and the selected-country KPIs) are never empty on first paint. No
  // URL write on mount -> history stays clean; ?country only appears on a click.
  const selectedCode = computed<string>(() => {
    if (country.value) return country.value
    return leaderRows.value.find((r) => r.selectable)?.code ?? ''
  })
  const selectedRow = computed(() =>
    rows.value.find((r) => countryCodeOf(r) === selectedCode.value),
  )
  const selectedName = computed(() =>
    selectedRow.value
      ? countryDisplayName(selectedRow.value.country_code, selectedRow.value.country)
      : countryDisplayName(selectedCode.value),
  )
  const detailSubline = computed(() => {
    const r = selectedRow.value
    if (!r) return ''
    return `${fmtNumber(r.sessions)} sessions · ${fmtNumber(r.attempts)} attempts`
  })

  // Mobile drill: list until a country is tapped (?country set), then detail.
  // Desktop shows both panes (the data-attr display rules are @media-scoped).
  const mobileView = computed(() => (country.value ? 'detail' : 'list'))

  // Per-country credential dictionaries + source networks. Lazy (enabled once a
  // country is selected) and not part of the initial suspense -- the leaderboard
  // paints first; keepPreviousData holds the prior country while switching.
  const detailQuery = computed(() => ({ country: selectedCode.value, top_n: 8 }))
  const passwordsQ = useQuery(
    computed(() => ({
      ...statsTopCredentialsOptions({ query: { by: 'password', ...detailQuery.value } }),
      enabled: Boolean(selectedCode.value),
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  const usernamesQ = useQuery(
    computed(() => ({
      ...statsTopCredentialsOptions({ query: { by: 'username', ...detailQuery.value } }),
      enabled: Boolean(selectedCode.value),
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  const asnsQ = useQuery(
    computed(() => ({
      ...statsAsnsOptions({ query: { country: selectedCode.value, top_n: 6 } }),
      enabled: Boolean(selectedCode.value),
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )

  const passwordRows = computed(() =>
    buildCredentialFieldRows(passwordsQ.data.value ?? [], 'password'),
  )
  const usernameRows = computed(() =>
    buildCredentialFieldRows(usernamesQ.data.value ?? [], 'username'),
  )
  const asnRows = computed(() => buildAsnRows(asnsQ.data.value ?? []))
  // First load of a country's breakdown (no prior data to hold). Distinct from
  // an empty bucket so the lists don't flash "none yet" before they resolve.
  const detailPending = computed(() => Boolean(selectedCode.value) && passwordsQ.isPending.value)

  // Announce the selected country + its breakdown once it resolves, so a screen
  // reader hears the detail panel change (the swap is otherwise silent). Cleared
  // while pending so the polite region speaks the resolved state, not the
  // loading flash.
  const selectionAnnouncement = computed(() => {
    if (!selectedCode.value || detailPending.value) return ''
    return detailSubline.value
      ? `Showing ${selectedName.value}. ${detailSubline.value}.`
      : `Showing ${selectedName.value}.`
  })

  // After the first successful load, cached data stays on screen even if a
  // background poll fails; surface that so numbers are not silently stale.
  const isStale = computed(
    () =>
      countriesQ.isError.value ||
      passwordsQ.isError.value ||
      usernamesQ.isError.value ||
      asnsQ.isError.value,
  )

  // --- URL writes (preserve the non-default sort + explicit country) ----------
  function pushQuery(patch: Record<string, string | undefined>): void {
    const q: Record<string, string> = {}
    if (sort.value !== 'sessions') q.sort = sort.value
    if (country.value) q.country = country.value
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined || v === '') delete q[k]
      else q[k] = v
    }
    void router.push({ query: q })
  }
  const selectCountry = (code: string): void => pushQuery({ country: code })
  const backToList = (): void => pushQuery({ country: undefined })
  const setSort = (s: CountrySort): void => pushQuery({ sort: s === 'sessions' ? undefined : s })

  // Mobile drill focus move (WCAG 2.4.3): the list<->detail swap hides the
  // control the user just activated. On a phone, move focus to the entered
  // pane so keyboard/SR users keep their place; desktop shows both panes, so
  // skip it there. Not immediate -> a deep-linked ?country on mount does not
  // steal focus (AppShell already moves it to <main>).
  const backBtnRef = ref<HTMLButtonElement | null>(null)
  const listRef = ref<HTMLElement | null>(null)
  const isMobile = (): boolean => window.matchMedia('(max-width: 768px)').matches
  watch(
    () => country.value,
    (cur) => {
      void nextTick(() => {
        if (!isMobile()) return
        if (cur) backBtnRef.value?.focus()
        else listRef.value?.focus()
      })
    },
  )
</script>

<template>
  <div class="countries">
    <PageHeader title="Countries" />

    <!-- Announce the selected country + its breakdown; the detail-panel swap is
         otherwise silent to a screen reader. -->
    <div class="visually-hidden" role="status" aria-live="polite">{{ selectionAnnouncement }}</div>

    <p v-if="isStale" class="stale" role="status">⚠ data may be stale — retrying</p>

    <section class="stats-grid" aria-label="Country totals">
      <Card padding="sm">
        <Stat :value="fmtNumber(totalCountries)" label="Countries" />
      </Card>
      <Card padding="sm">
        <Stat :value="geoPctLabel" label="Geo-resolved" />
      </Card>
      <Card padding="sm">
        <Stat
          :value="fmtNumber(selectedRow?.distinct_ips ?? 0)"
          label="Unique IPs"
          :delta="selectedName"
        />
      </Card>
      <Card padding="sm">
        <Stat
          :value="fmtSuccessRate(selectedRow?.success_rate ?? null)"
          label="Success rate"
          :delta="selectedName"
        />
      </Card>
    </section>

    <div class="body" :data-mobile-view="mobileView">
      <Card fill class="leaderboard">
        <template #title>
          <div class="lb-head">
            <h2 class="lb-title">Countries</h2>
            <div class="seg" role="radiogroup" aria-label="Rank countries by">
              <button
                v-for="s in COUNTRY_SORTS"
                :key="s.id"
                type="button"
                role="radio"
                class="seg-btn"
                :class="{ 'seg-btn-active': sort === s.id }"
                :aria-checked="sort === s.id"
                @click="setSort(s.id)"
              >
                {{ s.label }}
              </button>
            </div>
          </div>
        </template>

        <div ref="listRef" class="lb-scroll" tabindex="-1">
          <ul v-if="leaderRows.length" class="lb-list" :aria-label="leaderboardLabel">
            <li v-for="(row, i) in leaderRows" :key="row.key">
              <button
                v-if="row.selectable"
                type="button"
                class="lb-row"
                :class="{ 'lb-row-active': row.code === selectedCode }"
                :aria-current="row.code === selectedCode ? 'true' : undefined"
                :aria-label="`${i + 1}. ${row.label}, ${row.valueLabel}`"
                :title="row.title"
                @click="selectCountry(row.code)"
              >
                <span class="lb-name">{{ row.label }}</span>
                <span class="lb-track" aria-hidden="true">
                  <span class="lb-fill" :style="{ '--bar-w': row.widthPct }" />
                </span>
                <span class="lb-value">{{ row.valueLabel }}</span>
              </button>
              <div v-else class="lb-row lb-row-static" :title="row.title">
                <span class="lb-name">{{ row.label }}</span>
                <span class="lb-track" aria-hidden="true">
                  <span class="lb-fill" :style="{ '--bar-w': row.widthPct }" />
                </span>
                <span class="lb-value">{{ row.valueLabel }}</span>
              </div>
            </li>
          </ul>
          <EmptyState v-else title="No country data yet" />
        </div>
      </Card>

      <Card fill class="detail">
        <template #title>
          <div class="dt-head">
            <button ref="backBtnRef" type="button" class="back-btn" @click="backToList">
              <svg class="back-chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS['chevron-left']" />
              </svg>
              Countries
            </button>
            <div class="dt-headings">
              <h2 class="dt-title">{{ selectedName || 'Select a country' }}</h2>
              <p v-if="selectedCode" class="dt-subline">{{ detailSubline }}</p>
            </div>
          </div>
        </template>

        <div v-if="selectedCode" class="dt-scroll">
          <p v-if="detailPending" class="dt-loading" role="status">Loading breakdown…</p>
          <template v-else>
            <!-- Three equal slots so the section headers sit at constant
                 positions regardless of each list's length (no jump when
                 switching country); each list scrolls inside its own slot. -->
            <section class="dt-section">
              <h3 class="dt-sub">Top passwords</h3>
              <div class="dt-section-body">
                <BarList
                  :items="passwordRows"
                  label="Top passwords from this country"
                  empty-text="No passwords from here yet"
                />
              </div>
            </section>
            <section class="dt-section">
              <h3 class="dt-sub">Top usernames</h3>
              <div class="dt-section-body">
                <BarList
                  :items="usernameRows"
                  label="Top usernames from this country"
                  empty-text="No usernames from here yet"
                />
              </div>
            </section>
            <section class="dt-section">
              <h3 class="dt-sub">Top networks (ASN)</h3>
              <div class="dt-section-body">
                <BarList
                  :items="asnRows"
                  label="Top source networks for this country"
                  empty-text="No network data yet"
                />
              </div>
            </section>
          </template>
        </div>
        <EmptyState
          v-else
          title="Select a country"
          hint="Pick a country from the list to see its credentials and source networks."
        />
      </Card>
    </div>
  </div>
</template>

<style scoped>
  .countries {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    /* Fill the shell so .body flexes to the leftover height; page fits the
       viewport with no desktop scroll. */
    flex: 1 1 auto;
    min-height: 0;
  }

  .stale {
    flex: 0 0 auto;
    margin: 0;
    font-size: var(--type-xs);
    color: var(--warning);
  }

  .stats-grid {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-3);
  }

  /* Master-detail: leaderboard (narrower) + the selected country's breakdown.
     Both columns own their own scroll, so the page never scrolls on desktop. */
  .body {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
    gap: var(--space-3);
  }

  .leaderboard,
  .detail {
    min-height: 0;
  }

  /* Leaner card headers so the title rows don't eat the panes' vertical space
     (Card's default is --space-4). */
  .leaderboard :deep(.card-header),
  .detail :deep(.card-header) {
    margin-bottom: var(--space-2);
  }

  /* --- leaderboard ---------------------------------------------------------- */
  .lb-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .lb-title {
    margin: 0;
    font-size: var(--type-base);
    line-height: var(--type-base-lh);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .seg {
    display: inline-flex;
    gap: 2px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 2px;
  }

  .seg-btn {
    border: 0;
    background: transparent;
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 500;
    /* Coarse-pointer 44px target (--control-h scales up on touch). */
    min-height: var(--control-h);
    padding: 4px 10px;
    border-radius: calc(var(--radius-sm) - 1px);
    cursor: pointer;
    transition:
      color var(--motion-fast) ease,
      background var(--motion-fast) ease;
  }

  .seg-btn:hover {
    color: var(--text);
  }

  .seg-btn-active {
    background: var(--surface);
    color: var(--accent);
  }

  .seg-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  /* The list owns the leftover card height and scrolls inside it (the page does
     not scroll on desktop). scrollbar-gutter:stable keeps the row width steady. */
  .lb-scroll {
    height: 100%;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }
  .lb-scroll:focus {
    outline: none;
  }
  .lb-scroll:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .lb-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .lb-row {
    width: 100%;
    display: grid;
    /* Fixed value column so every bar starts/ends at the same x regardless of
       the trailing number's width. */
    grid-template-columns: minmax(0, 1.2fr) minmax(48px, 1.4fr) 4.5rem;
    align-items: center;
    gap: var(--space-3);
    /* button reset */
    border: 1px solid transparent;
    background: transparent;
    text-align: left;
    cursor: pointer;
    min-height: var(--control-h);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    transition:
      background var(--motion-fast) ease,
      border-color var(--motion-fast) ease;
  }

  .lb-row-static {
    cursor: default;
  }

  button.lb-row:hover {
    background: var(--surface-hover);
  }

  .lb-row-active,
  button.lb-row-active:hover {
    background: var(--surface);
    border-color: var(--border);
  }

  .lb-row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .lb-name {
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lb-row-active .lb-name {
    color: var(--accent);
    font-weight: 600;
  }

  .lb-track {
    height: 6px;
    background: var(--bg-2);
    border-radius: 999px;
    overflow: hidden;
  }

  .lb-fill {
    display: block;
    height: 100%;
    width: var(--bar-w);
    background: var(--accent);
    border-radius: 999px;
    transition: width var(--motion-base) ease;
  }

  .lb-value {
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  /* --- detail --------------------------------------------------------------- */
  .dt-head {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  /* Hidden on desktop (both panes visible); the mobile drill reveals it. */
  .back-btn {
    display: none;
    flex: 0 0 auto;
    align-items: center;
    gap: 4px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    min-height: var(--control-h);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    transition:
      background var(--motion-fast) ease,
      border-color var(--motion-fast) ease;
  }
  .back-btn:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }
  .back-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .back-chevron {
    width: 1.1em;
    height: 1.1em;
    fill: currentColor;
    flex: 0 0 auto;
    /* nudge off the optical right-bias of the chevron glyph */
    margin-left: -2px;
  }

  .dt-headings {
    min-width: 0;
  }

  .dt-title {
    margin: 0;
    font-size: var(--type-base);
    line-height: var(--type-base-lh);
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dt-subline {
    margin: 0;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .dt-scroll {
    height: 100%;
    min-height: 0;
    /* Three equal slots so the section headers stay at fixed positions (top,
       one-third, two-thirds) no matter how long each list is. The panel itself
       never scrolls -- each list scrolls inside its own slot when it overflows. */
    display: grid;
    grid-template-rows: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
    overflow: hidden;
  }

  .dt-section {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .dt-section-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    /* reserve the gutter so the bars line up whether or not a slot scrolls */
    scrollbar-gutter: stable;
  }

  .dt-loading {
    margin: 0;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
  }

  .dt-sub {
    flex: 0 0 auto;
    margin: 0 0 var(--space-2);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }

  /* --- mobile (<=768px): drill navigation, page scrolls -------------------- */
  @media (max-width: 768px) {
    /* Stop hard-fitting: the panes show their full content and the page scrolls
       (the proven Credentials/Activity play). */
    .countries {
      overflow-y: auto;
    }
    /* 2x2 KPIs so big numbers / "81.3%" never clip or side-scroll. */
    .stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    /* Keep the selected-country KPI cards a stable height: force the delta (the
       country name) onto its own line so a short value like "—" can't pull it
       inline and shrink the card relative to a wide "42.6%". */
    .stats-grid :deep(.stat-delta) {
      flex-basis: 100%;
    }
    /* Master-detail can't sit side-by-side: stack to a content-height column and
       show one pane at a time (drill navigation). */
    .body {
      display: flex;
      flex-direction: column;
      flex: 0 0 auto;
    }
    .body[data-mobile-view='list'] .detail {
      display: none;
    }
    .body[data-mobile-view='detail'] .leaderboard {
      display: none;
    }
    /* Un-trap the fill cards: content height + block body so the whole pane shows
       and the PAGE scrolls (not the pane). */
    .leaderboard,
    .detail {
      flex: 0 0 auto;
      height: auto;
    }
    .leaderboard :deep(.card-body),
    .detail :deep(.card-body) {
      display: block;
    }
    .lb-scroll,
    .dt-scroll {
      height: auto;
      overflow: visible;
    }
    /* No bounded panel height on mobile (the page scrolls), so the fixed-thirds
       split is meaningless -- stack the sections at content height and let each
       list grow, with the page handling the scroll. */
    .dt-scroll {
      display: flex;
      flex-direction: column;
    }
    .dt-section-body {
      overflow: visible;
    }
    /* The 3 sort buttons as a tidy full-width row. */
    .seg {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      width: 100%;
    }
    /* Reveal the back affordance on the detail screen. */
    .back-btn {
      display: inline-flex;
    }
  }
</style>
