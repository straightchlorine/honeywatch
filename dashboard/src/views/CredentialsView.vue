<script setup lang="ts"></script>

<template>
  <div class="credentials">
    <header class="credentials-head">
      <h1 class="credentials-title">Credentials</h1>
      <p class="credentials-sub">Captured authentication attempts.</p>
    </header>
    <p class="placeholder">Coming soon.</p>
  </div>
</template>

<style scoped>
.credentials {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.credentials-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.credentials-title {
  margin: 0;
  font-size: var(--type-xl);
  line-height: var(--type-xl-lh);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}

.credentials-sub {
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
