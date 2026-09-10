<script setup lang="ts">
  /**
   * 100dvh flex column on desktop (no page scroll), natural height on mobile.
   * `head` slot is the topbar; `default` slot is the page body.
   */
  import { onMounted, ref } from 'vue'
  import { useRoute } from 'vue-router'
  import { useIsFetching } from '@tanstack/vue-query'

  withDefaults(
    defineProps<{
      /** Map view goes edge-to-edge under transparent topbar overlay. */
      fullBleed?: boolean
    }>(),
    { fullBleed: false },
  )

  const route = useRoute()
  const isFetching = useIsFetching()

  // Route-change a11y (WCAG 4.1.3, 2.4.3): announce new page and focus <main>.
  // Module-level flag skips initial document load; subsequent mounts fire announcement.
  let hasNavigated = false
  const routeAnnounce = ref('')
  onMounted(() => {
    if (hasNavigated) {
      routeAnnounce.value = (route.meta.title as string | undefined) ?? 'Honeywatch'
      // preventScroll: scrollBehavior handles scrolling (including back/forward restore).
      document.getElementById('main')?.focus({ preventScroll: true })
    }
    hasNavigated = true
  })
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main">Skip to main content</a>
    <div class="visually-hidden" role="status" aria-live="polite">{{ routeAnnounce }}</div>
    <slot name="head" />
    <main
      id="main"
      tabindex="-1"
      class="page"
      :class="{ 'full-bleed': fullBleed }"
      :aria-busy="isFetching > 0"
    >
      <slot />
    </main>
  </div>
</template>

<style scoped>
  .shell {
    position: relative;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* No outline for programmatic focus (route change). */
  .page:focus {
    outline: none;
  }

  .skip-link {
    position: absolute;
    left: 12px;
    top: 12px;
    padding: 8px 12px;
    background: var(--accent);
    color: var(--bg-0);
    border-radius: var(--radius-md);
    font-weight: 600;
    transform: translateY(-200%);
    transition: transform var(--motion-fast) ease;
    z-index: 100;
  }

  .skip-link:focus-visible {
    transform: translateY(0);
    outline: 2px solid var(--accent-strong);
    outline-offset: 2px;
  }

  .page {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 16px 22px 18px;
    /* Floor is the old fixed cap, so 1080p and below render exactly as before;
       84vw only exceeds it past ~2048px, so only genuinely large displays get
       the extra room instead of leaving half a 4K screen empty. */
    max-width: clamp(1720px, 84vw, 2400px);
    width: 100%;
    margin: 0 auto;
  }

  .page.full-bleed {
    padding: 0;
    max-width: none;
  }

  @media (max-width: 900px) {
    .shell {
      height: auto;
      min-height: 100dvh;
      overflow: visible;
      /* `clip` prevents DrawerShell's translateX(103%) from widening the layout
         viewport, while keeping vertical scroll visible. */
      overflow-x: clip;
    }

    .page {
      padding: 12px 14px 24px;
    }

    .page.full-bleed {
      padding: 0;
    }
  }
</style>
