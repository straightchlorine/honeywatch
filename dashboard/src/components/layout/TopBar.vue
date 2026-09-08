<script setup lang="ts">
  import { onMounted, ref } from 'vue'
  import HexIcon from '../base/HexIcon.vue'
  import AboutOverlay from './AboutOverlay.vue'
  import { ICONS } from '../icons'
  import { useHwTooltip } from '../../composables/useHwTooltip'
  import { useStaleData } from '../../composables/useStaleData'

  const PAGES = [
    { name: 'overview', to: '/', label: 'Overview' },
    { name: 'pulse', to: '/pulse', label: 'Pulse' },
    { name: 'origins', to: '/origins', label: 'Origins' },
    { name: 'credentials', to: '/credentials', label: 'Credentials' },
    { name: 'sessions', to: '/sessions', label: 'Sessions' },
    { name: 'payloads', to: '/payloads', label: 'Payloads' },
  ] as const

  const {
    current,
    overlay = false,
  } = defineProps<{
    /** Page name (prefix-matched by callers so e.g. session detail keeps Sessions lit). */
    current?: string
    /** Transparent gradient bar over the map deck instead of the solid header. */
    overlay?: boolean
  }>()

  const aboutOpen = ref(false)
  const navEl = ref<HTMLElement | null>(null)
  const tt = useHwTooltip()

  // Lives in the chrome, not the page: a warning here cannot reflow the view under it.
  const { stale } = useStaleData()
  const STALE_TEXT =
    'Updates are failing, so these numbers may be out of date. Still retrying.'

  // scrollLeft (not scrollIntoView) prevents vertical scroll; onMounted (not watch)
  // because watch fires before layout under Suspense.
  onMounted(() => {
    const nav = navEl.value
    const active = nav?.querySelector<HTMLElement>('[aria-current="page"]')
    if (nav && active)
      nav.scrollLeft = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2
  })

  function onAbout(e: MouseEvent): void {
    e.preventDefault()
    // replaceState (not a real navigation) so opening About never adds a back-
    // button entry; the URL still carries #about for deep-linking/sharing.
    history.replaceState(null, '', `${location.pathname}${location.search}#about`)
    aboutOpen.value = true
  }
</script>

<template>
  <header class="topbar" :class="{ overlay }">
    <RouterLink class="brand" to="/" aria-label="Honeywatch">
      <HexIcon :size="20" />
      <span class="brand-text">Honeywatch</span>
    </RouterLink>

    <!-- tabindex: axe scrollable-region-focusable (nav overflows horizontally on mobile) -->
    <nav ref="navEl" class="nav" aria-label="Main" tabindex="0">
      <RouterLink
        v-for="p in PAGES"
        :key="p.name"
        :to="p.to"
        :aria-current="current === p.name ? 'page' : undefined"
      >
        {{ p.label }}
      </RouterLink>
    </nav>

    <span
      v-if="stale"
      class="tb-stale"
      role="status"
      @pointerenter="tt.show(STALE_TEXT)"
      @pointermove="tt.move($event)"
      @pointerleave="tt.hide()"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path :d="ICONS.warning" />
      </svg>
      <span class="visually-hidden">{{ STALE_TEXT }}</span>
    </span>

    <a class="tb-about" href="#about" @click="onAbout">About</a>

    <a
      class="tb-gh"
      href="https://github.com/straightchlorine/honeywatch"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="GitHub repository"
      @pointerenter="tt.show('GitHub repository')"
      @pointermove="tt.move($event)"
      @pointerleave="tt.hide()"
      @focus="tt.show('GitHub repository')"
      @blur="tt.hide()"
    >
      <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path :d="ICONS.github" />
      </svg>
    </a>
  </header>

  <AboutOverlay v-model="aboutOpen" />
</template>

<style scoped>
  .topbar {
    height: 54px;
    flex: none;
    display: flex;
    align-items: center;
    gap: 26px;
    padding: 0 22px;
    background: color-mix(in srgb, var(--bg-1) 88%, transparent);
    backdrop-filter: blur(10px);
    z-index: 40;
  }

  .topbar.overlay {
    position: absolute;
    inset: 0 0 auto 0;
    background: linear-gradient(rgba(14, 10, 7, 0.85), rgba(14, 10, 7, 0.35));
    backdrop-filter: blur(12px);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 17px;
    letter-spacing: 0.01em;
    color: var(--text);
  }

  .brand:hover {
    text-decoration: none;
  }

  .brand svg {
    filter: drop-shadow(0 0 6px var(--accent-glow));
  }

  .nav {
    display: flex;
    gap: 2px;
    margin: 0 auto;
  }

  .nav:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .nav a {
    padding: 7px 13px;
    border-radius: 999px;
    color: var(--text-muted);
    font-size: 13.5px;
    font-weight: 550;
    transition:
      color var(--motion-fast),
      background var(--motion-fast);
  }

  .nav a:hover {
    color: var(--text);
    background: var(--surface-hover);
    text-decoration: none;
  }

  .nav a[aria-current='page'] {
    color: var(--bg-0);
    background: var(--accent);
    font-weight: 650;
  }

  /* margin-left:auto anchors the right-hand cluster to the far edge. */
  .tb-stale {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    color: var(--warning);
    flex: none;
  }

  .tb-stale + .tb-about {
    margin-left: 0;
  }

  .tb-about {
    font-size: 13px;
    font-weight: 550;
    color: var(--text-muted);
    padding: 6px 10px;
    border-radius: 999px;
  }

  .tb-about:hover {
    color: var(--text);
    background: var(--surface-hover);
    text-decoration: none;
  }

  .tb-gh {
    color: var(--text-muted);
    display: inline-flex;
    padding: 6px;
    border-radius: var(--radius-md);
  }

  .tb-gh:hover {
    color: var(--text);
  }

  .tb-gh svg {
    width: 17px;
    height: 17px;
  }

  @media (max-width: 480px) {
    .brand-text {
      display: none;
    }
  }

  @media (max-width: 900px) {
    .topbar {
      gap: 12px;
      padding: 0 12px;
    }

    /* The repo link is not worth a slot in a bar this narrow; the nav needs it. */
    .tb-gh {
      display: none;
    }

    .nav {
      flex: 1;
      margin: 0;
      overflow-x: auto;
      scrollbar-width: none;
      /* offsetLeft must be nav-relative for scrolling calculations */
      position: relative;
      /* fade the clipped edges so half-visible pills read as scrollable */
      mask-image: linear-gradient(
        to right,
        transparent,
        #000 16px,
        #000 calc(100% - 16px),
        transparent
      );
    }

    .nav a {
      white-space: nowrap;
    }
  }
</style>
