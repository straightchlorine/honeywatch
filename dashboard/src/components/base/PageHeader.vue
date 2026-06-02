<script setup lang="ts">
  defineProps<{ title: string; sub?: string }>()
</script>

<template>
  <header class="page-head">
    <h1 class="page-title">{{ title }}</h1>
    <p v-if="sub" class="page-sub">{{ sub }}</p>
  </header>
</template>

<style scoped>
  .page-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .page-title {
    margin: 0;
    font-size: var(--type-xl);
    line-height: var(--type-xl-lh);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
  }

  .page-sub {
    margin: 0;
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
  }
</style>
