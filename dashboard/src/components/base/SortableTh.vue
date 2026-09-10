<script setup lang="ts">
  /**
   * One column header, shared by every sortable table. Omit sortKey for a column
   * that cannot be ranked and it renders a plain th instead.
   * The API ranks each key in one fixed direction (only `country` is A-Z), so
   * `dir` describes the server's order - this is not a toggle, and re-clicking
   * the active column does nothing.
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
  const sort = defineModel<string>()

  const active = computed(() => props.sortKey !== undefined && sort.value === props.sortKey)
  const ariaSort = computed<'ascending' | 'descending' | undefined>(() => {
    if (!active.value) return undefined
    return props.dir === 'asc' ? 'ascending' : 'descending'
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
        @click="sort = sortKey"
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
            :transform="dir === 'asc' ? 'rotate(-90 12 12)' : 'rotate(90 12 12)'"
          />
        </svg>
        <span v-if="active" class="visually-hidden">{{ dir === 'asc' ? 'sorted ascending' : 'sorted descending' }}</span>
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
