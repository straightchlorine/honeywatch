<script setup lang="ts">
  /**
   * Pill filter button with optional trailing control slot (e.g. InfoDot).
   * Trailing control wraps as a sibling rather than nesting (invalid HTML
   * for nested buttons) and shares styling to read as one control.
   */
  defineProps<{ pressed?: boolean }>()
  const emit = defineEmits<{ toggle: [] }>()
</script>

<template>
  <span class="chip-wrap">
    <button type="button" class="chip" :aria-pressed="pressed ?? false" @click="emit('toggle')">
      <slot />
    </button>
    <span v-if="$slots.trailing" class="chip-trailing">
      <slot name="trailing" />
    </span>
  </span>
</template>

<style scoped>
  .chip-wrap {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  /* Fill and border on wrapper, not chip, so the trailing icon is included
     in the pressed state and reads as one control. */
  .chip-wrap:has(.chip-trailing) {
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    padding-right: 10px;
    gap: 2px;
    transition: all var(--motion-fast);
  }

  .chip-wrap:has(.chip-trailing) .chip {
    border-color: transparent;
    background: transparent;
  }

  .chip-wrap:has(.chip-trailing):hover,
  .chip-wrap:has(.chip:hover, .chip-trailing:hover) {
    border-color: var(--accent-dim);
  }

  .chip-wrap:has(.chip-trailing):has(.chip[aria-pressed='true']) {
    background: var(--accent);
    border-color: var(--accent);
  }

  .chip-wrap:has(.chip-trailing):has(.chip[aria-pressed='true']) .chip {
    color: var(--bg-0);
    font-weight: 650;
  }

  .chip-wrap:has(.chip-trailing):has(.chip[aria-pressed='true']) .chip-trailing :deep(.info-btn) {
    color: var(--bg-0);
  }

  .chip-wrap:has(.chip-trailing):has(.chip[aria-pressed='true']) .chip-trailing :deep(.info-btn:hover) {
    background: transparent;
  }

  .chip {
    appearance: none;
    border: 1px solid var(--border-strong);
    background: transparent;
    color: var(--text-muted);
    font: 550 12.5px var(--font-sans);
    padding: 6px 12px;
    border-radius: 999px;
    cursor: pointer;
    min-height: var(--control-h);
    transition: all var(--motion-fast);
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .chip:hover {
    border-color: var(--accent-dim);
    color: var(--text);
  }

  .chip[aria-pressed='true'] {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-0);
    font-weight: 650;
  }

  .chip-trailing {
    display: inline-flex;
    align-items: center;
  }

  /* Chips share a row with a card title on mobile, so they shed padding rather
     than pushing each other onto separate lines. 24px keeps the WCAG 2.5.8
     target because the whole pill stays tappable. */
  @media (max-width: 900px) {
    .chip {
      font-size: 12px;
      padding: 4px 10px;
      min-height: 26px;
      gap: 4px;
    }

    .chip-wrap:has(.chip-trailing) {
      padding-right: 6px;
    }
  }
</style>
