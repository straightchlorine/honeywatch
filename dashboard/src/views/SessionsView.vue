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
import { classifySession } from '@/utils/sessionClass'

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
    .map((c) => ({ value: c.country_code as string, label: (c.country ?? c.country_code) as string })),
])

const rows = computed(() =>
  (sessionsQ.data.value?.items ?? []).map((s) => ({ ...s, cls: classifySession(s) })),
)
const meta = computed(() => sessionsQ.data.value!.meta)

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
              <RouterLink :to="{ name: 'session-detail', params: { id: row.id } }">
                {{ shortId(row.id) }}
              </RouterLink>
            </td>
            <td>
              <span class="badge" :class="`badge-${row.cls.kind}`" :title="row.cls.title">
                {{ row.cls.label }}
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
}

.filters {
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
  overflow-x: auto;
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
  color: var(--text-muted);
  font-weight: 600;
  font-size: var(--type-xs);
  letter-spacing: 0.02em;
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
  display: inline-block;
  padding: 1px var(--space-2);
  border-radius: var(--radius-sm);
  border: 1px solid currentcolor;
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
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
</style>
