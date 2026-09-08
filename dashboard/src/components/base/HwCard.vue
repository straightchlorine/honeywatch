<script setup lang="ts">
  const {
    title,
    note,
    glass = false,
  } = defineProps<{
    title?: string
    note?: string
    /** Frosted floating variant (map deck overlays, live feed). */
    glass?: boolean
  }>()
</script>

<template>
  <section class="card" :class="{ glass }">
    <h2 v-if="title || note || $slots['head-extra']">
      {{ title }}
      <span v-if="note" class="note">{{ note }}</span>
      <slot name="head-extra" />
    </h2>
    <slot />
  </section>
</template>

<style scoped>
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 16px 18px;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .card.glass {
    background: var(--glass);
    border-color: var(--glass-border);
    backdrop-filter: blur(14px) saturate(1.15);
    box-shadow: var(--shadow-md);
  }

  .card > h2 {
    margin: 0 0 10px;
    font-size: 13px;
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .card > h2 .note {
    text-transform: none;
    letter-spacing: 0;
    font-weight: 450;
    color: var(--text-dim);
    margin-left: auto;
    font-size: 12px;
  }

  /* Narrow screens cannot fit title and trailing content on one line; the title
     keeps the row to itself and everything else drops below it. */
  @media (max-width: 900px) {
    .card > h2 {
      flex-wrap: wrap;
      row-gap: 6px;
    }

    .card > h2 .note {
      margin-left: 0;
      flex-basis: 100%;
    }
  }
</style>
