<script setup lang="ts">
  /** 'ok'/'bad' tones reserved for auth outcomes, not series colors. */
  defineProps<{ tone: 'amber' | 'ok' | 'bad' | 'dim' }>()
</script>

<template>
  <span class="badge" :class="tone"><slot /></span>
</template>

<style scoped>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 999px;
    font: 600 11px var(--font-mono);
    letter-spacing: 0.02em;
    border: 1px solid transparent;
    white-space: nowrap;
  }

  .badge.amber {
    color: var(--accent-hot);
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.25);
  }
  .badge.ok {
    color: var(--ok);
    background: rgba(132, 204, 22, 0.1);
    border-color: rgba(132, 204, 22, 0.28);
  }
  .badge.bad {
    color: var(--bad);
    background: rgba(248, 113, 113, 0.09);
    border-color: rgba(248, 113, 113, 0.26);
  }
  .badge.dim {
    color: var(--text-dim);
    background: var(--surface-2);
    border-color: var(--border);
  }
</style>
