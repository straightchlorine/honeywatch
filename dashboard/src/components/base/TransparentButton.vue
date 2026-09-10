<script setup lang="ts">
  import { RouterLink } from 'vue-router'
  import type { RouteLocationRaw } from 'vue-router'

  const { to } = defineProps<{
    to?: RouteLocationRaw
  }>()

  const emit = defineEmits<{ click: [] }>()

  const handleClick = () => {
    if (!to) {
      emit('click')
    }
  }
</script>

<template>
  <RouterLink
    v-if="to"
    :to="to"
    class="transparent-button"
  >
    <slot />
  </RouterLink>
  <button
    v-else
    type="button"
    class="transparent-button"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

<style scoped>
  .transparent-button {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 9px 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--accent-dim);
    background: transparent;
    color: var(--text);
    font-size: 13px;
    font-weight: 600;
    font-family: var(--font-sans);
    min-height: var(--control-h);
    cursor: pointer;
    transition: all var(--motion-fast);
    text-decoration: none;
  }

  .transparent-button:hover {
    text-decoration: none;
  }

  .transparent-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
</style>
