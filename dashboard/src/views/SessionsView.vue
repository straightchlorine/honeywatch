<script setup lang="ts">
  import { computed } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import { listSessionsOptions, statsTopCountriesOptions } from '@/api/queries'
  import PageHeader from '@/components/base/PageHeader.vue'
  import Pagination from '@/components/base/Pagination.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import Dropdown from '@/components/base/Dropdown.vue'
  import { fmtRelativeTime } from '@/utils/format'
  import { humanizeDuration } from '@/utils/duration'
  import { sessionClass } from '@/utils/sessionClass'

  type Opt = { value: string; label: string }

  const PER_PAGE = 25

  type Sort = 'recent' | 'country' | 'active'
  type Category = 'active' | 'login' | 'failed' | 'probe'
  const SORTS: Sort[] = ['recent', 'country', 'active']
  const CATEGORIES: Category[] = ['active', 'login', 'failed', 'probe']

  const SORT_OPTIONS: Opt[] = [
    { value: 'recent', label: 'Most recent' },
    { value: 'country', label: 'Country A–Z' },
    { value: 'active', label: 'Most active' },
  ]
  const CATEGORY_OPTIONS: Opt[] = [
    { value: '', label: 'All sessions' },
    { value: 'active', label: 'CLI' },
    { value: 'login', label: 'Successful login' },
    { value: 'failed', label: 'Failed auth' },
    { value: 'probe', label: 'Probe' },
  ]

  const route = useRoute()
  const router = useRouter()

  // All browse state lives in the URL so a filtered view is shareable + reloadable.
  const page = computed(() => Math.max(1, Number(route.query.page) || 1))
  const sort = computed<Sort>(() => {
    const s = route.query.sort
    return typeof s === 'string' && (SORTS as string[]).includes(s) ? (s as Sort) : 'recent'
  })
  const category = computed<Category | ''>(() => {
    const c = route.query.category
    return typeof c === 'string' && (CATEGORIES as string[]).includes(c) ? (c as Category) : ''
  })
  const country = computed(() => {
    const c = route.query.country
    return typeof c === 'string' && /^[A-Za-z]{2}$/.test(c) ? c.toUpperCase() : ''
  })
  const filtersActive = computed(() => Boolean(category.value || country.value))

  const sessionsQ = useQuery(
    computed(() => ({
      ...listSessionsOptions({
        query: {
          page: page.value,
          per_page: PER_PAGE,
          sort: sort.value,
          ...(category.value ? { category: category.value } : {}),
          ...(country.value ? { country: country.value } : {}),
        },
      }),
      placeholderData: keepPreviousData,
    })),
  )
  await sessionsQ.suspense()

  // Country options reuse the top-countries leaderboard (max 100). Not awaited:
  // the table is the primary content and must render even if this lags or fails.
  const countriesQ = useQuery({ ...statsTopCountriesOptions({ query: { top_n: 100 } }) })
  const countryOptions = computed<Opt[]>(() => [
    { value: '', label: 'All countries' },
    ...(countriesQ.data.value ?? [])
      .filter((c) => c.country_code && /^[A-Za-z]{2}$/.test(c.country_code))
      .map((c) => ({
        value: c.country_code as string,
        label: (c.country ?? c.country_code) as string,
      })),
  ])

  const rows = computed(() =>
    (sessionsQ.data.value?.items ?? []).map((s) => ({ ...s, cls: sessionClass(s) })),
  )
  const meta = computed(() => sessionsQ.data.value!.meta)
  // keepPreviousData holds the prior page if a filter/page change fails to load;
  // surface that rather than showing stale rows as if they were current.
  const isStale = computed(() => sessionsQ.isError.value)

  // Merge one filter into the URL and reset to page 1 (the result set changed).
  function setParam(key: string, value: string | boolean): void {
    const query: Record<string, string> = {}
    for (const [k, v] of Object.entries(route.query)) {
      if (k !== 'page' && typeof v === 'string') query[k] = v
    }
    if (value === '' || value === false) delete query[key]
    else query[key] = String(value)
    void router.push({ query })
  }

  // 'recent' is the default sort, so drop it from the URL to keep links clean.
  function onSort(value: string): void {
    setParam('sort', value === 'recent' ? '' : value)
  }

  function goToPage(p: number): void {
    void router.push({ query: { ...route.query, page: String(p) } })
  }

  function shortId(id: string): string {
    return id.length > 14 ? `${id.slice(0, 14)}…` : id
  }
</script>

<template>
  <div class="sessions">
    <PageHeader title="Sessions" sub="Recent honeypot sessions. Open one to replay the terminal." />

    <p v-if="isStale" class="stale" role="status">⚠ data may be stale — retrying</p>

    <div class="filters" role="group" aria-label="Session filters">
      <div class="field">
        <span id="f-sort-label" class="field-label">Sort</span>
        <Dropdown
          button-id="f-sort"
          label-id="f-sort-label"
          :model-value="sort"
          :options="SORT_OPTIONS"
          @update:model-value="onSort"
        />
      </div>

      <div class="field">
        <span id="f-category-label" class="field-label">Show</span>
        <Dropdown
          button-id="f-category"
          label-id="f-category-label"
          :model-value="category"
          :options="CATEGORY_OPTIONS"
          @update:model-value="(v) => setParam('category', v)"
        />
      </div>

      <div class="field">
        <span id="f-country-label" class="field-label">Country</span>
        <Dropdown
          button-id="f-country"
          label-id="f-country-label"
          :model-value="country"
          :options="countryOptions"
          @update:model-value="(v) => setParam('country', v)"
        />
      </div>
    </div>

    <div class="table-wrap">
      <table class="sessions-table">
        <caption class="visually-hidden">
          Honeypot sessions, filtered and paginated.
        </caption>
        <thead>
          <tr>
            <th scope="col">Session</th>
            <th scope="col">Activity</th>
            <th scope="col">Source country</th>
            <th scope="col">Protocol</th>
            <th scope="col">Started</th>
            <th scope="col">Duration</th>
            <th scope="col" class="num">Auth attempts</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" v-memo="[row.id, row.cls.kind, row.ended_at]">
            <td class="id">
              <RouterLink :to="{ name: 'session-detail', params: { id: row.id } }" :title="row.id">
                {{ shortId(row.id) }}
              </RouterLink>
            </td>
            <td>
              <span class="badge" :class="`badge-${row.cls.kind}`" :title="row.cls.title">
                <span class="badge-glyph" aria-hidden="true">{{ row.cls.glyph }}</span>
                <span class="badge-label">{{ row.cls.label }}</span>
              </span>
            </td>
            <td>{{ row.country ?? row.country_code ?? '—' }}</td>
            <td>{{ row.protocol }}</td>
            <td>
              <time v-if="row.started_at" :datetime="row.started_at" :title="row.started_at">
                {{ fmtRelativeTime(row.started_at) }}
              </time>
              <template v-else>—</template>
            </td>
            <td>{{ humanizeDuration(row.started_at, row.ended_at) }}</td>
            <td class="num">{{ row.auth_attempt_count }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Mobile layout: the 7-column table side-scrolls unusably on phones, so
           below --bp-md it is hidden and each session renders as a card. -->
      <ul class="session-cards" aria-label="Honeypot sessions">
        <li v-for="row in rows" :key="row.id" class="session-card">
          <div class="card-head">
            <RouterLink
              class="card-id"
              :to="{ name: 'session-detail', params: { id: row.id } }"
              :title="row.id"
            >
              {{ shortId(row.id) }}
            </RouterLink>
            <span class="badge" :class="`badge-${row.cls.kind}`" :title="row.cls.title">
              <span class="badge-glyph" aria-hidden="true">{{ row.cls.glyph }}</span>
              <span class="badge-label">{{ row.cls.label }}</span>
            </span>
          </div>
          <dl class="card-facts">
            <div class="fact">
              <dt>Country</dt>
              <dd>{{ row.country ?? row.country_code ?? '—' }}</dd>
            </div>
            <div class="fact">
              <dt>Protocol</dt>
              <dd>{{ row.protocol }}</dd>
            </div>
            <div class="fact">
              <dt>Started</dt>
              <dd>
                <time v-if="row.started_at" :datetime="row.started_at" :title="row.started_at">
                  {{ fmtRelativeTime(row.started_at) }}
                </time>
                <template v-else>—</template>
              </dd>
            </div>
            <div class="fact">
              <dt>Duration</dt>
              <dd>{{ humanizeDuration(row.started_at, row.ended_at) }}</dd>
            </div>
            <div class="fact">
              <dt>Auth attempts</dt>
              <dd>{{ row.auth_attempt_count }}</dd>
            </div>
          </dl>
        </li>
      </ul>

      <EmptyState
        v-if="!rows.length"
        :title="filtersActive ? 'No sessions match these filters' : 'No sessions yet'"
        :hint="
          filtersActive
            ? 'Try widening the filters above.'
            : 'Sessions appear here as the honeypot captures activity.'
        "
      />
    </div>

    <Pagination
      v-if="meta.pages > 1"
      :page="page"
      :pages="meta.pages"
      :total="meta.total"
      @update:page="goToPage"
    />
  </div>
</template>

<style scoped>
  .sessions {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    /* The table is the flexing hero with its own scroll, so the page fits the
     viewport with no outer scroll (header + filters + pagination stay fixed). */
    flex: 1 1 auto;
    min-height: 0;
  }

  .stale {
    flex: 0 0 auto;
    margin: 0;
    font-size: var(--type-xs);
    color: var(--warning);
  }

  .filters {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-3) var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .field-label {
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-dim);
    font-weight: 600;
  }

  .table-wrap {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
  }

  .sessions-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--type-sm);
  }

  .sessions-table th,
  .sessions-table td {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--border);
  }

  .sessions-table th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--bg-1);
    color: var(--text-muted);
    font-weight: 600;
    font-size: var(--type-xs);
    letter-spacing: 0.02em;
  }

  /* Card layout is desktop-hidden; the table is the default presentation. */
  .session-cards {
    display: none;
    list-style: none;
    margin: 0;
    padding: 0;
    flex-direction: column;
    gap: var(--space-3);
  }

  .session-card {
    padding: var(--space-3);
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }

  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .card-id {
    font-family: var(--font-mono);
    font-size: var(--type-sm);
  }

  .card-facts {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  .card-facts .fact {
    display: flex;
    flex-direction: column;
  }

  .card-facts dt {
    font-size: var(--type-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }

  .card-facts dd {
    margin: 0;
    font-size: var(--type-sm);
    color: var(--text);
  }

  .sessions-table td.num,
  .sessions-table th.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .sessions-table td.id {
    font-family: var(--font-mono);
  }

  .badge {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    padding: 1px var(--space-2);
    border-radius: var(--radius-sm);
    border: 1px solid currentcolor;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  /* Non-color cue so the class is distinguishable in grayscale (WCAG 1.4.1). */
  .badge-glyph {
    font-family: var(--font-mono);
    font-weight: 700;
  }

  .badge-active {
    color: var(--accent);
  }
  .badge-login {
    color: var(--warning);
  }
  .badge-failed {
    color: var(--error);
  }
  .badge-probe {
    color: var(--text-dim);
  }

  @media (max-width: 768px) {
    .sessions-table {
      display: none;
    }
    .session-cards {
      display: flex;
    }

    /* Keep the three filters on one row: the Dropdown's 160px min-width forced a
     2+1 wrap. Drop it to equal columns; long values (country names) ellipsize on
     the trigger -- the open list still shows them in full. */
    .filters {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      align-items: end;
      gap: var(--space-2);
      padding: var(--space-3);
    }
    .field {
      min-width: 0;
    }
    .field :deep(.dropdown) {
      display: flex;
    }
    .field :deep(.dd-button) {
      min-width: 0;
      width: 100%;
    }
    /* flex:1 + min-width:0 let the value shrink below its content width -- without
     it the flex child keeps min-width:auto and text-overflow never fires, so a
     long country name overflows the trigger instead of ellipsizing. */
    .field :deep(.dd-value) {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* The Country list (rightmost column, wide country names) opened past the right
     edge; .shell-main's overflow-y:auto then made the x-axis scrollable and the
     page slid sideways. Open it right-aligned, cap it to the viewport, and let
     long names wrap so the list can never reach beyond the screen. */
    .field:last-child :deep(.dd-list) {
      left: auto;
      right: 0;
      max-width: calc(100vw - 2 * var(--space-4));
    }
    .field :deep(.dd-option) {
      white-space: normal;
    }
  }
</style>
