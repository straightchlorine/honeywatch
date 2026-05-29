<script setup lang="ts">
import Card from '@/components/base/Card.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import PageHeader from '@/components/base/PageHeader.vue'
</script>

<template>
  <section class="not-found">
    <PageHeader title="Route not found" sub="The page you requested doesn't exist." />
    <Card>
      <EmptyState title="Route not found" hint="The page you requested doesn't exist.">
        <RouterLink to="/" class="back-link">Back to overview</RouterLink>
      </EmptyState>
    </Card>
  </section>
</template>

<style scoped>
  .not-found {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .back-link {
    color: var(--accent);
    text-decoration: none;
    font-weight: 600;
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    margin-top: var(--space-3);
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .back-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }
</style>
