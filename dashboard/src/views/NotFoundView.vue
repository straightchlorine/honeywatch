<script setup lang="ts">
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar />
    </template>

    <div class="not-found">
      <div class="page-head">
        <h1>Page not found</h1>
        <span class="sub">The page you requested doesn't exist.</span>
      </div>

      <HwCard class="card">
        <EmptyState title="Page not found" hint="The page you requested doesn't exist.">
          <RouterLink to="/" class="back-link">Back to overview</RouterLink>
        </EmptyState>
      </HwCard>
    </div>
  </PageShell>
</template>

<style scoped>
  .not-found {
    display: flex;
    flex-direction: column;
    gap: 14px;
    flex: 1 1 auto;
    min-height: 0;
  }

  .page-head {
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex: none;
  }

  .page-head h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 700;
  }

  .sub {
    color: var(--text-dim);
    font-size: 13px;
  }

  .card {
    flex: none;
  }

  .back-link {
    color: var(--accent);
    text-decoration: none;
    font-weight: 600;
    font-size: 14px;
    margin-top: 12px;
    display: inline-block;
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .back-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-md);
  }

  @media (max-width: 760px) {
    .page-head {
      flex-wrap: wrap;
      gap: 4px;
    }

    .page-head h1 {
      font-size: 22px;
      flex-basis: 100%;
    }

    .sub {
      flex-basis: 100%;
    }
  }
</style>
