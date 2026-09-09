<script setup lang="ts">
  /**
   * First-visit overlay: auto-dismisses after ~5s. Opened via link/deep link: stays until dismissed.
   */
  import { onMounted, onUnmounted, ref } from 'vue'
  import HexIcon from '../base/HexIcon.vue'
  import IconLink from '../IconLink.vue'
  import { ICONS } from '../icons'
  import { readStored, writeStored } from '@/utils/safeStorage'

  const open = defineModel<boolean>({ default: false })

  const SEEN_KEY = 'hw-seen-about'
  const AUTO_DISMISS_MS = 5200
  let autoTimer: ReturnType<typeof setTimeout> | undefined
  // Set only during first-visit auto-fade; hides the "closes on its own" hint when opened deliberately.
  const autoDismissing = ref(false)

  // Any interaction inside the card means the visitor is reading: stop the clock.
  function holdOpen(): void {
    clearTimeout(autoTimer)
    autoDismissing.value = false
  }

  function stripHash(): void {
    if (location.hash === '#about') {
      history.replaceState(null, '', location.pathname + location.search)
    }
  }

  function dismiss(): void {
    holdOpen()
    open.value = false
    stripHash()
  }

  function onBackdropClick(e: MouseEvent): void {
    if (e.target === e.currentTarget) dismiss()
  }

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && open.value) dismiss()
  }

  function onHashChange(): void {
    if (location.hash === '#about') open.value = true
  }

  onMounted(() => {
    const firstVisit = !readStored('localStorage', SEEN_KEY)
    if (location.hash === '#about') {
      open.value = true // deep link: stays open, no timer
    } else if (firstVisit) {
      open.value = true
      autoDismissing.value = true
      autoTimer = setTimeout(dismiss, AUTO_DISMISS_MS)
    }
    if (firstVisit) writeStored('localStorage', SEEN_KEY, '1')
    window.addEventListener('hashchange', onHashChange)
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    clearTimeout(autoTimer)
    window.removeEventListener('hashchange', onHashChange)
    window.removeEventListener('keydown', onKeydown)
  })
</script>

<template>
  <Transition name="intro-fade">
    <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
    <div
      v-if="open"
      class="intro"
      role="dialog"
      aria-modal="true"
      aria-label="About Honeywatch"
      @click="onBackdropClick"
    >
      <!-- eslint-disable-next-line vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
      <div class="intro-card glass" @click="holdOpen">
        <HexIcon :size="44" />
        <h2>Honeywatch</h2>
        <p>
          Honeywatch is a honeypot monitoring system. Server in Helsinki let's attackers in on
          purpose and records everything they do.
        </p>
        <p>
          Watch them on map, analyze commands they ran, what they downloaded and see what they were
          after.
        </p>
        <details class="intro-more">
          <summary>About the map</summary>
          <p>Borders follow the Natural Earth dataset. Dotted lines mark disputed borders.</p>
          <p>
            Detailed borders can feel slow on a phone or a big screen. The
            <strong>Map detail</strong> control starts at <i>Regular</i> - pick <i>Low</i> for
            simpler outlines that draw faster, or <i>High</i> for the sharpest ones.
          </p>
        </details>
        <div class="intro-authors">
          <span class="author">
            Piotr Krzysztof Lis
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/straightchlorine/"
              label="Piotr on LinkedIn"
            />
            <IconLink
              icon="github"
              href="https://github.com/straightchlorine"
              label="Piotr on GitHub"
            />
            <IconLink
              icon="codeberg"
              href="https://codeberg.org/piotrkrzysztof"
              label="Piotr on Codeberg"
            />
          </span>
          <span class="author">
            Jakub Kucharski
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/jakub-kucharski-360811305/"
              label="Jakub on LinkedIn"
            />
            <IconLink icon="github" href="https://github.com/kubson2002k" label="Jakub on GitHub" />
          </span>
        </div>
        <button type="button" class="intro-enter" @click="dismiss">
          Enter
          <svg
            class="arrow-icon"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </button>
        <div v-if="autoDismissing" class="intro-hint">
          Closes on its own - find it again under About.
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
  .intro-fade-enter-active,
  .intro-fade-leave-active {
    transition: opacity var(--motion-slow) ease;
  }
  .intro-fade-enter-from,
  .intro-fade-leave-to {
    opacity: 0;
  }

  .intro {
    /* Fixed position anchors to viewport; 100dvh enables internal scrolling on mobile. */
    position: fixed;
    inset: 0;
    height: 100dvh;
    z-index: 30;
    display: flex;
    /* margin: auto centers without clipping overflow; align-items: center would hide the top on mobile. */
    overflow-y: auto;
    padding: 16px 0;
    background: rgba(14, 10, 7, 0.55);
    backdrop-filter: blur(5px);
  }

  .intro-card {
    margin: auto;
    flex: 0 0 auto;
    width: min(480px, calc(100% - 48px));
    border-radius: var(--radius-lg);
    padding: 34px 38px 26px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }

  .intro-card h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 30px;
    font-weight: 800;
  }

  .intro-card p {
    margin: 0;
    color: var(--text-muted);
    font-size: 14px;
    line-height: 1.65;
  }

  .intro-more {
    width: 100%;
    text-align: left;
  }

  .intro-more summary {
    cursor: pointer;
    text-align: center;
    font: 500 11.5px var(--font-mono);
    color: var(--text-dim);
    list-style: none;
  }

  .intro-more summary::-webkit-details-marker {
    display: none;
  }

  .intro-more summary::after {
    content: ' +';
  }

  .intro-more[open] summary::after {
    content: ' -';
  }

  .intro-more summary:hover {
    color: var(--text-muted);
  }

  .intro-more p {
    margin: 10px 0 0;
    color: var(--text-dim);
    font-size: 12px;
    line-height: 1.55;
  }

  .intro-more strong {
    color: var(--accent-hot);
    font-weight: 650;
  }

  /* One author per line, each line centred as a unit rather than left-aligned
     against the widest name. */
  .intro-authors {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    font-size: 12.5px;
    color: var(--text);
    font-weight: 600;
  }

  .author {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  .intro-enter {
    margin-top: 4px;
    padding: 10px 22px;
    border-radius: 999px;
    border: none;
    background: var(--accent);
    color: var(--bg-0);
    font: 650 14px var(--font-sans);
    cursor: pointer;
  }

  .intro-enter:hover {
    background: var(--accent-hot);
  }

  .arrow-icon {
    display: inline;
    width: 14px;
    height: 14px;
    margin-left: 4px;
    vertical-align: -0.125em;
  }

  .intro-hint {
    font: 500 11px var(--font-mono);
    color: var(--text-dim);
  }

  @media (max-width: 900px) {
    .intro-card {
      padding: 24px 20px 20px;
    }
    .intro-authors {
      flex-direction: column;
      gap: 8px;
    }
  }
</style>
