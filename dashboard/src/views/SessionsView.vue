<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, keepPreviousData } from '@tanstack/vue-query'
import { listSessionsOptions } from '@/api/queries'
import PageHeader from '@/components/base/PageHeader.vue'

const page = ref(1)
const perPage = ref(20)

const sessions = useQuery(
  computed(() => ({
    ...listSessionsOptions({ query: { page: page.value, per_page: perPage.value } }),
    placeholderData: keepPreviousData,
  })),
)

await sessions.suspense()

const items = computed(() => sessions.data.value!.items)
const meta = computed(() => sessions.data.value!.meta)
const totalPages = computed(() => meta.value.pages)

function prevPage() {
  if (page.value > 1) page.value -= 1
}

function nextPage() {
  if (page.value < totalPages.value) page.value += 1
}
</script>

<template>
  <div class="sessions">
    <PageHeader title="Sessions" sub="Recent honeypot sessions." />

    <div>
      <table class="sessions-table">
        <caption class="visually-hidden">
          Recent honeypot sessions, paginated.
        </caption>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Source country</th>
            <th scope="col">Protocol</th>
            <th scope="col">Started</th>
            <th scope="col">Ended</th>
            <th scope="col" class="num">Auth attempts</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="items.length === 0">
            <td colspan="6" class="empty">No sessions yet.</td>
          </tr>
          <tr
            v-for="row in items"
            :key="row.id"
            v-memo="[row.id, row.ended_at, row.auth_attempt_count]"
          >
            <td>
              <RouterLink :to="{ name: 'session-detail', params: { id: row.id } }">
                {{ row.id }}
              </RouterLink>
            </td>
            <td>{{ row.country ?? row.country_code ?? '—' }}</td>
            <td>{{ row.protocol }}</td>
            <td>{{ row.started_at ?? '—' }}</td>
            <td>{{ row.ended_at ?? '—' }}</td>
            <td class="num">{{ row.auth_attempt_count }}</td>
          </tr>
        </tbody>
      </table>

      <div class="pagination">
        <button
          type="button"
          class="page-btn"
          aria-label="Previous page"
          :disabled="page === 1"
          @click="prevPage"
        >
          Prev
        </button>
        <span class="page-info" role="status">
          Page {{ meta.page }} of {{ meta.pages }} ({{ meta.total }} total)
        </span>
        <button
          type="button"
          class="page-btn"
          aria-label="Next page"
          :disabled="page >= totalPages"
          @click="nextPage"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sessions {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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

.empty {
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-4);
}

.pagination {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-3);
}

.page-btn {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  cursor: pointer;
  transition:
    background var(--motion-fast) ease,
    border-color var(--motion-fast) ease;
}

.page-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.page-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  color: var(--text-muted);
  font-size: var(--type-xs);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
