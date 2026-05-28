<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, keepPreviousData } from '@tanstack/vue-query'
import { listSessionsOptions } from '@/api/queries'

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
    <header class="sessions-head">
      <h1 class="sessions-title">Sessions</h1>
      <p class="sessions-sub">Recent honeypot sessions.</p>
    </header>

    <div>
      <table class="sessions-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Source country</th>
            <th>Protocol</th>
            <th>Started</th>
            <th>Ended</th>
            <th class="num">Auth attempts</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="items.length === 0">
            <td colspan="6" class="empty">No sessions yet.</td>
          </tr>
          <tr v-for="row in items" :key="row.id">
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
        <button :disabled="page === 1" @click="prevPage">Prev</button>
        <span class="page-info">
          Page {{ meta.page }} of {{ meta.pages }} ({{ meta.total }} total)
        </span>
        <button :disabled="page >= totalPages" @click="nextPage">Next</button>
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

.sessions-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sessions-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.sessions-sub {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
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
  border-bottom: 1px solid var(--border, #2a2a2a);
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

.page-info {
  color: var(--text-muted);
  font-size: var(--type-xs);
}
</style>
