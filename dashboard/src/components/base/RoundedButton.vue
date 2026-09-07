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
    class="rounded-button"
    role="button"
  >
    <slot />
  </RouterLink>
  <button
    v-else
    type="button"
    class="rounded-button"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

<style scoped>
  .rounded-button {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 9px 0;
    border-radius: var(--radius-md);
    border: 1px solid var(--accent);
    background: var(--accent);
    color: var(--bg-0);
    font-size: 13px;
    font-weight: 600;
    font-family: var(--font-sans);
    min-height: var(--control-h);
    cursor: pointer;
    transition: all var(--motion-fast);
    text-decoration: none;
  }

  .rounded-button:hover {
    text-decoration: none;
  }
</style>
