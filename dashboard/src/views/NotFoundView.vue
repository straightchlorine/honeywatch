<script setup lang="ts">
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import HexIcon from '@/components/base/HexIcon.vue'
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar />
    </template>

    <EmptyState
      class="not-found"
      title="Page not found"
      hint="The page you requested doesn't exist."
      :heading-level="1"
    >
      <template #icon>
        <HexIcon :size="44" class="hex" />
      </template>
      <RouterLink to="/" class="back-link">Back to overview</RouterLink>
    </EmptyState>
  </PageShell>
</template>

<style scoped>
  /* Fills the shell body so the empty state centres on desktop and mobile. */
  .not-found {
    flex: 1 1 auto;
    min-height: 0;
  }

  .not-found :deep(.empty-title) {
    font-family: var(--font-display);
    font-size: 26px;
    line-height: 1.2;
    font-weight: 700;
  }

  .hex {
    margin-bottom: var(--space-2);
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    margin-top: var(--space-3);
    padding: 0 22px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--bg-0);
    font-weight: 650;
    font-size: 14px;
    text-decoration: none;
  }

  .back-link:hover {
    background: var(--accent-hot);
    text-decoration: none;
  }

  .back-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  @media (max-width: 900px) {
    /* Shell is natural-height on mobile; give the body a viewport-based floor. */
    .not-found {
      min-height: 60dvh;
    }
  }
</style>
