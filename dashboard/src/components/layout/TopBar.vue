<script setup lang="ts">
  import { ref } from 'vue'
  import HexIcon from '../base/HexIcon.vue'
  import AboutOverlay from './AboutOverlay.vue'
  import { ICONS } from '../icons'
  import { useHwTooltip } from '../../composables/useHwTooltip'
  import { useStaleData } from '../../composables/useStaleData'

  const PAGES = [
    { name: 'overview', to: '/', label: 'Overview', icon: 'globe' },
    { name: 'pulse', to: '/pulse', label: 'Pulse', icon: 'pulse' },
    { name: 'origins', to: '/origins', label: 'Origins', icon: 'pin' },
    { name: 'credentials', to: '/credentials', label: 'Credentials', icon: 'key' },
    { name: 'sessions', to: '/sessions', label: 'Sessions', icon: 'terminal' },
    { name: 'payloads', to: '/payloads', label: 'Payloads', icon: 'file' },
  ] as const

  const { current, overlay = false } = defineProps<{
    /** Page name (prefix-matched by callers so e.g. session detail keeps Sessions lit). */
    current?: string
    /** Transparent gradient bar over the map deck instead of the solid header. */
    overlay?: boolean
  }>()

  const aboutOpen = ref(false)
  const tt = useHwTooltip()

  // Lives in the chrome, not the page: a warning here cannot reflow the view under it.
  const { stale } = useStaleData()
  const STALE_TEXT = 'Updates are failing, so these numbers may be out of date. Still retrying.'

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

    <!-- Below 760px this same nav becomes the fixed bottom tab bar (icons shown). -->
    <nav class="nav" aria-label="Main">
      <RouterLink
        v-for="p in PAGES"
        :key="p.name"
        :to="p.to"
        :aria-current="current === p.name ? 'page' : undefined"
      >
        <svg class="ni" viewBox="0 0 24 24" aria-hidden="true">
          <path :d="ICONS[p.icon]" />
        </svg>
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
      aria-label="GitHub"
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

  .ni {
    display: none;
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

  /* ::after grows the hit area only; visual size is unchanged. */
  @media (min-width: 760px) and (pointer: coarse) {
    .nav a,
    .tb-about {
      position: relative;
    }
    .nav a::after,
    .tb-about::after {
      content: '';
      position: absolute;
      inset: -7px 0;
    }
    .nav {
      padding: 2px 0;
    }
  }

  @media (max-width: 900px) {
    .topbar {
      gap: 12px;
      padding: 0 12px;
    }

    .nav {
      flex: 1;
      margin: 0;
    }

    .nav a,
    .tb-about {
      display: inline-flex;
      align-items: center;
      min-height: 40px;
    }

    .nav a {
      white-space: nowrap;
    }
  }

  /* The inline nav (760-900px) needs the slot; under 760px it lives in the bottom
     bar, so the repo link comes back with a 44px touch target. */
  @media (min-width: 760px) and (max-width: 900px) {
    .tb-gh {
      display: none;
    }
  }

  /* Bottom tab bar: six equal slots, glyph over label. z-index 15 (not the topbar's 40)
     keeps drawers (20) above it; backdrop-filter would make the topbar the containing
     block of this fixed bar, so it goes. */
  @media (max-width: 759.98px) {
    .topbar,
    .topbar.overlay {
      backdrop-filter: none;
    }

    .topbar:not(.overlay) {
      z-index: auto;
    }

    /* 16, not 40: the nav inside would otherwise paint over the About dialog (30). */
    .topbar.overlay {
      z-index: 16;
    }

    .tb-gh {
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      padding: 0;
      margin-right: -8px;
    }

    .tb-about {
      margin-left: auto;
    }

    .nav {
      position: fixed;
      inset: auto 0 0;
      z-index: 15;
      height: var(--bottomnav-h);
      padding: 5px 2px env(safe-area-inset-bottom, 0px);
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      background: var(--bg-1);
      border-top: 1px solid var(--border);
    }

    .nav a {
      flex-direction: column;
      justify-content: center;
      gap: 3px;
      min-height: 0;
      padding: 0;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;
      line-height: 1.2;
    }

    /* The active pill moves to the glyph: a full-slot fill leaves no room around
       "Credentials" at 360px. Label takes the accent too. */
    .nav a:hover,
    .nav a[aria-current='page'] {
      background: none;
    }

    .nav a[aria-current='page'] {
      color: var(--accent);
      font-weight: 500;
    }

    .ni {
      display: block;
      box-sizing: border-box;
      width: 46px;
      height: 26px;
      padding: 4px 14px;
      border-radius: 999px;
      fill: currentColor;
      transition: background var(--motion-fast);
    }

    .nav a[aria-current='page'] .ni {
      background: var(--accent);
      fill: var(--bg-0);
    }
  }
</style>
