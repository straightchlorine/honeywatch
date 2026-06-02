<script setup lang="ts">
  import { computed } from 'vue'

  /**
   * Reusable prev/next pagination control. Extracted from the (deferred)
   * SessionsView so its styling is ready to drop into any future paginated view.
   * `v-model:page` friendly — emits the clamped target page on prev/next.
   */
  const props = defineProps<{ page: number; pages: number; total?: number }>()
  const emit = defineEmits<{ 'update:page': [page: number] }>()

  const canPrev = computed(() => props.page > 1)
  const canNext = computed(() => props.page < props.pages)

  function prev() {
    if (canPrev.value) emit('update:page', props.page - 1)
  }
  function next() {
    if (canNext.value) emit('update:page', props.page + 1)
  }
</script>

<template>
  <div class="pagination">
    <button
      type="button"
      class="page-btn"
      aria-label="Previous page"
      :disabled="!canPrev"
      @click="prev"
    >
      Prev
    </button>
    <span class="page-info" role="status">
      Page {{ page }} of {{ pages
      }}<template v-if="total !== undefined"> ({{ total }} total)</template>
    </span>
    <button
      type="button"
      class="page-btn"
      aria-label="Next page"
      :disabled="!canNext"
      @click="next"
    >
      Next
    </button>
  </div>
</template>

<style scoped>
  .pagination {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-3);
  }

  .page-btn {
    min-height: var(--control-h);
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

  @media (max-width: 768px) {
    .pagination {
      justify-content: center;
    }
  }
</style>
