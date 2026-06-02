<script setup lang="ts">
  import EmptyState from '@/components/base/EmptyState.vue'
  import Tooltip from '@/components/base/Tooltip.vue'
  import { useTooltip } from '@/components/base/useTooltip'
  import { fmtNumber } from '@/utils/format'

  type Row = { key: string; label: string; count: number; widthPct: string; title?: string }

  defineProps<{ items: Row[]; label: string; emptyText?: string }>()

  // Themed tooltip in place of the native title= hover (full label for truncated
  // rows). Mouse-only sugar: the row text itself is the accessible value.
  const tt = useTooltip()
</script>

<template>
  <ul v-if="items.length" class="bar-list" :aria-label="label">
    <li
      v-for="row in items"
      :key="row.key"
      v-memo="[row.key, row.count, row.widthPct]"
      class="bar-row"
    >
      <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
      <span
        class="bar-label"
        :title="row.title ?? row.label"
        @mouseenter="tt.show(row.title ?? row.label, $event)"
        @mousemove="tt.show(row.title ?? row.label, $event)"
        @mouseleave="tt.hide()"
        >{{ row.label }}</span
      >
      <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
      <span class="bar-track" aria-hidden="true">
        <span class="bar-fill" :style="{ '--bar-w': row.widthPct }" />
      </span>
      <span class="bar-value">{{ fmtNumber(row.count) }}</span>
    </li>
  </ul>
  <EmptyState v-else :title="emptyText ?? 'No data'" />
  <Tooltip v-bind="tt.state" />
</template>

<style scoped>
  .bar-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .bar-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(80px, 2fr) auto;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
  }

  .bar-label {
    color: var(--text);
    font-family: var(--font-mono);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bar-track {
    height: 6px;
    background: var(--bg-2);
    border-radius: 999px;
    overflow: hidden;
  }

  .bar-fill {
    display: block;
    height: 100%;
    width: var(--bar-w);
    background: var(--accent);
    border-radius: 999px;
    transition: width var(--motion-base) ease;
  }

  .bar-value {
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    text-align: right;
    min-width: 3ch;
  }
</style>
