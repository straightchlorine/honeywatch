<script setup lang="ts">
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { ICONS } from '@/components/icons'

  defineProps<{
    /** The tooltip title - also prefixed to the aria-label. */
    title: string
    /** The tooltip explanation - suffixed to the aria-label as "title: text". */
    text: string
  }>()

  const tt = useHwTooltip()
</script>

<template>
  <button
    type="button"
    tabindex="0"
    class="info-btn"
    :aria-label="`${title}: ${text}`"
    @pointerenter="tt.show(title, [['', text]])"
    @pointermove="tt.move($event)"
    @pointerleave="tt.hide()"
    @focus="tt.show(title, [['', text]])"
    @blur="tt.hide()"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path :d="ICONS.info" />
    </svg>
  </button>
</template>

<style scoped>
  .info-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 0.25rem;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color 120ms ease,
      background 120ms ease;
    flex-shrink: 0;
  }

  .info-btn:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  .info-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
  }

  .info-btn svg {
    width: 0.75rem;
    height: 0.75rem;
    fill: currentColor;
  }
</style>
