<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const ipHash = computed(() => String(route.params.hash ?? ''))
</script>

<template>
  <div class="ip">
    <header class="ip-head">
      <h1 class="ip-title">IP {{ ipHash }}</h1>
      <p class="ip-sub">Activity from this source address.</p>
    </header>
    <p class="placeholder">Coming soon.</p>
  </div>
</template>

<style scoped>
.ip {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.ip-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ip-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
  font-family: var(--font-mono);
}

.ip-sub {
  margin: 0;
  color: var(--text-muted);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
}

.placeholder {
  color: var(--text-muted);
  font-size: var(--type-sm);
}
</style>
