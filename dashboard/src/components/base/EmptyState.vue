<script setup lang="ts">
  withDefaults(
    defineProps<{
      title: string
      hint?: string
      icon?: string
      headingLevel?: 2 | 3 | 4
    }>(),
    { headingLevel: 2 },
  )
</script>

<template>
  <div class="empty">
    <div v-if="icon" class="empty-icon" aria-hidden="true">{{ icon }}</div>
    <component :is="`h${headingLevel}`" class="empty-title">{{ title }}</component>
    <p v-if="hint" class="empty-hint">{{ hint }}</p>
    <slot />
  </div>
</template>

<style scoped>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: var(--space-6) var(--space-4);
    gap: var(--space-2);
    color: var(--text-muted);
  }

  .empty-icon {
    font-size: var(--type-2xl);
    line-height: 1;
    color: var(--text-dim);
    margin-bottom: var(--space-2);
  }

  .empty-title {
    margin: 0;
    font-size: var(--type-lg);
    line-height: var(--type-lg-lh);
    font-weight: 600;
    color: var(--text);
  }

  .empty-hint {
    margin: 0;
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    color: var(--text-muted);
    max-width: 32rem;
  }
</style>
