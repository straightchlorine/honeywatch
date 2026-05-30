<script setup lang="ts">
  import { computed, useSlots } from 'vue'

  type Padding = 'sm' | 'md' | 'lg'

  /**
   * Title precedence: the `title` slot wins over the `title` prop. If both are
   * given, the slot replaces the default heading entirely (callers can render
   * their own heading + actions). If only `title` prop is set, a heading of
   * `headingLevel` (default h2, since cards sit directly under a page h1) is
   * rendered so the document outline stays contiguous.
   */
  const props = withDefaults(
    defineProps<{
      title?: string
      padding?: Padding
      headingLevel?: 2 | 3 | 4
      /** Fill the parent's height and let the body flex (for hero panes). */
      fill?: boolean
    }>(),
    { padding: 'md', headingLevel: 2, fill: false },
  )

  const slots = useSlots()
  const hasTitleSlot = computed(() => Boolean(slots.title))
  const hasHeader = computed(() => Boolean(props.title) || hasTitleSlot.value)

  const paddingClass = computed(() => `pad-${props.padding}`)
</script>

<template>
  <div class="card" :class="[paddingClass, { 'card-fill': fill }]">
    <header v-if="hasHeader" class="card-header">
      <slot name="title">
        <component :is="`h${headingLevel}`" v-if="title" class="card-title">
          {{ title }}
        </component>
      </slot>
    </header>
    <div class="card-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
  .card {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    box-shadow: var(--shadow-sm);
  }

  .pad-sm {
    padding: var(--space-3);
  }

  .pad-md {
    padding: var(--space-5);
  }

  .pad-lg {
    padding: var(--space-6);
  }

  .card-header {
    margin-bottom: var(--space-4);
  }

  .card-title {
    margin: 0;
    font-size: var(--type-lg);
    line-height: var(--type-lg-lh);
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
  }

  .card-body {
    color: var(--text);
  }

  .card-fill {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .card-fill .card-body {
    flex: 1 1 auto;
    min-height: 0;
  }
</style>
