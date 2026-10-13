<script setup lang="ts">
  import HexIcon from './HexIcon.vue'
</script>

<template>
  <p class="insight">
    <HexIcon :size="12" filled class="bullet" />
    <span><slot /></span>
  </p>
</template>

<style scoped>
  .insight {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 10px 14px;
    margin: 0;
    border: 1px solid var(--accent-edge);
    border-radius: var(--radius-md);
    background: var(--accent-wash);
    font-size: 13px;
    color: var(--text-muted);
  }

  .bullet {
    flex: none;
    margin-top: 3px;
  }

  .insight :deep(b) {
    color: var(--text);
    font-weight: 620;
  }
</style>
