<script setup lang="ts">
  /**
   * One column header, shared by every sortable table. Omit sortKey for a column
   * that cannot be ranked and it renders a plain th instead.
   * Implements three-state cycling: click 1 sorts by this column in its natural
   * direction, click 2 reverses, click 3 clears the sort.
   */
  import { computed } from 'vue'
  import { ICONS } from '@/components/icons'

  interface Props {
    sortKey?: string
    dir?: 'asc' | 'desc'
    hint?: string
  }

  const props = withDefaults(defineProps<Props>(), {
    dir: 'desc',
  })
  const sort = defineModel<string | undefined>('sort')
  const order = defineModel<'asc' | 'desc' | undefined>('order')

  const active = computed(() => props.sortKey !== undefined && sort.value === props.sortKey)
  const resolvedDir = computed<'asc' | 'desc'>(() => order.value ?? props.dir)
  const ariaSort = computed<'ascending' | 'descending' | undefined>(() => {
    if (!active.value) return undefined
    return resolvedDir.value === 'asc' ? 'ascending' : 'descending'
  })

  function onClick(): void {
    if (!props.sortKey) return

    // Different column: set sort to this key, order to natural direction
    if (sort.value !== props.sortKey) {
      sort.value = props.sortKey
      order.value = props.dir
      return
    }

    // Active column: check if at natural direction
    if ((order.value ?? props.dir) === props.dir) {
      // Still at natural direction: flip it
      order.value = props.dir === 'asc' ? 'desc' : 'asc'
    } else {
      // Already flipped: clear both
      sort.value = undefined
      order.value = undefined
    }
  }

  // What the next click will do
  const nextActionText = computed<string>(() => {
    if (!active.value) return 'Sort by this column'
    if ((order.value ?? props.dir) === props.dir) {
      return `Sort in reverse`
    }
    return `Clear sort`
  })
</script>

<template>
  <th scope="col" :aria-sort="ariaSort">
    <template v-if="!sortKey">
      <slot />
    </template>
    <template v-else>
      <button
        type="button"
        :title="hint"
        @click="onClick"
      >
        <slot />
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          aria-hidden="true"
          focusable="false"
          class="sort-arrow"
          :class="{ active }"
        >
          <path
            :d="ICONS['chevron-right']"
            fill="currentColor"
            :transform="resolvedDir === 'asc' ? 'rotate(-90 12 12)' : 'rotate(90 12 12)'"
          />
        </svg>
        <span class="visually-hidden">
          {{ active ? `sorted ${resolvedDir === 'asc' ? 'ascending' : 'descending'}, ${nextActionText}` : nextActionText }}
        </span>
      </button>
    </template>
  </th>
</template>

<style scoped>
  th {
    position: relative;
  }

  button {
    appearance: none;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: inherit;
    font-size: inherit;
    font-weight: inherit;
    letter-spacing: inherit;
    text-transform: inherit;
    padding: 0;
    margin: 0;
    width: 100%;
  }

  button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .sort-arrow {
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s ease-out;
  }

  .sort-arrow.active {
    opacity: 1;
  }

  button:hover .sort-arrow,
  button:focus-visible .sort-arrow {
    opacity: 1;
  }
</style>
