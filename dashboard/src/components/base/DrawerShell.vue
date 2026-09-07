<script setup lang="ts">
  /**
   * Drawer chrome with WCAG-compliant focus trap, Escape-to-close, and
   * always-visible head bar for stable close affordance while content loads.
   */
  import { nextTick, useId, useTemplateRef, watch } from 'vue'
  import { useReducedMotion } from '@/composables/useReducedMotion'

  const { open, title, ariaLabel, labelledBy } = defineProps<{
    open: boolean
    title: string
    /** Overrides the default aria-labelledby (the title heading) for a caller
     *  whose visible title alone isn't a sufficient accessible name. */
    ariaLabel?: string
    labelledBy?: string
  }>()
  const emit = defineEmits<{ close: [] }>()

  const reduced = useReducedMotion()
  const titleId = useId()
  const panelRef = useTemplateRef<HTMLElement>('panel')

  // Element to return focus to on close - whatever had focus right before we
  // took it, not a fixed "opener" the caller has to track and pass in. The
  // map's country hits are SVG, not HTML, so both element families count.
  let returnFocusTo: HTMLElement | SVGElement | null = null

  const FOCUSABLE =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

  function focusables(): HTMLElement[] {
    if (!panelRef.value) return []
    return Array.from(panelRef.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  }

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      emit('close')
      return
    }
    if (e.key !== 'Tab') return
    const items = focusables()
    if (!items.length) return
    const first = items[0]!
    const last = items[items.length - 1]!
    const active = document.activeElement
    // "not contained" also catches focus having landed outside the panel
    // (e.g. a stray programmatic .focus() elsewhere) - pull it back in rather
    // than let Tab continue from wherever it ended up.
    const inPanel = panelRef.value?.contains(active) ?? false
    if (e.shiftKey) {
      if (!inPanel || active === first) {
        e.preventDefault()
        last.focus()
      }
    } else if (!inPanel || active === last) {
      e.preventDefault()
      first.focus()
    }
  }

  watch(
    () => open,
    async (isOpen, wasOpen) => {
      if (isOpen) {
        const active = document.activeElement
        returnFocusTo =
          active instanceof HTMLElement || active instanceof SVGElement ? active : null
        await nextTick()
        focusables()[0]?.focus({ preventScroll: true })
      } else if (wasOpen) {
        // Opener may be gone by now (a data refresh dropped that row) - fall
        // back to the page's own landing target (PageShell's #main) rather
        // than letting focus drop to document.body.
        const back = returnFocusTo?.isConnected ? returnFocusTo : document.getElementById('main')
        back?.focus({ preventScroll: true })
        returnFocusTo = null
      }
    },
  )
</script>

<template>
  <!-- keydown is a delegated Escape/Tab-trap handler for the whole dialog
       subtree - the aside itself isn't meant to be focused or clicked. -->
  <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -->
  <aside
    ref="panel"
    class="drawer"
    :class="{ open, 'no-motion': reduced }"
    role="dialog"
    aria-modal="true"
    :aria-label="ariaLabel"
    :aria-labelledby="ariaLabel ? undefined : (labelledBy ?? titleId)"
    :inert="!open"
    @keydown="onKeydown"
  >
    <div class="d-head">
      <slot name="head-extra" />
      <h2 :id="titleId">{{ title }}</h2>
      <button type="button" aria-label="Close" @click="emit('close')">&times;</button>
    </div>
    <slot />
  </aside>
</template>

<style scoped>
  .drawer {
    position: absolute;
    top: 54px;
    right: 0;
    bottom: 0;
    width: 384px;
    z-index: 20;
    border-left: 1px solid var(--glass-border);
    background: var(--glass);
    backdrop-filter: blur(12px);
    transform: translateX(103%);
    transition: transform var(--motion-slow) cubic-bezier(0.2, 0.8, 0.2, 1);
    display: flex;
    flex-direction: column;
    padding: 18px 20px;
    gap: 14px;
    overflow-y: auto;
    scrollbar-width: thin;
  }

  .drawer.no-motion {
    transition: none;
  }

  .drawer.open {
    transform: none;
    box-shadow: -24px 0 60px rgba(0, 0, 0, 0.45);
  }

  .d-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .d-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 21px;
    font-weight: 700;
  }
  .d-head button {
    margin-left: auto;
    background: none;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    color: var(--text-muted);
    width: 28px;
    height: 28px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
  }

  @media (max-width: 900px) {
    .drawer {
      width: 100%;
      border-left: 0;
    }
  }
</style>
