<script setup lang="ts">
import { computed } from "vue";

interface BarItem {
  label: string;
  count: number;
}

const props = defineProps<{
  title: string;
  items: BarItem[];
}>();

const max = computed(() =>
  props.items.reduce((m, d) => (d.count > m ? d.count : m), 1)
);
</script>

<template>
  <div class="panel">
    <h2 class="panel-title">{{ title }}</h2>
    <p v-if="items.length === 0" class="placeholder">No data</p>
    <ul v-else class="rows">
      <li v-for="item in items" :key="item.label" class="row">
        <span class="label" :title="item.label">{{ item.label }}</span>
        <span class="bar-track">
          <span class="bar-fill" :style="{ width: (item.count / max) * 100 + '%' }" />
        </span>
        <span class="count">{{ item.count.toLocaleString() }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.panel {
  background: #101419;
  border: 1px solid #1f242b;
  border-radius: 0.75rem;
  padding: 1.25rem 1.5rem;
}

.panel-title {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-bottom: 1rem;
}

.placeholder {
  color: var(--muted);
  font-size: 0.85rem;
  padding: 1.5rem 0;
  text-align: center;
}

.rows {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.row {
  display: grid;
  grid-template-columns: 8rem 1fr 3.5rem;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
}

.label {
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.bar-track {
  height: 0.5rem;
  background: #1a1f27;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  opacity: 0.85;
  min-width: 1px;
  transition: width 0.3s ease;
}

.count {
  color: var(--muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
