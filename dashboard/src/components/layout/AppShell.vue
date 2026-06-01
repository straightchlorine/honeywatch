<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useIsFetching } from '@tanstack/vue-query'
import IconLink from '../IconLink.vue'

const route = useRoute()
const routeAnnounce = ref('')

// /sessions and /sessions/:id are sibling route records, so RouterLink's
// record-based active matching won't keep the Sessions tab lit on the detail
// page. Drive it from a path prefix instead.
const sessionsActive = computed(() => route.path.startsWith('/sessions'))
// Reflect in-flight fetches (incl. keepPreviousData paging) so AT can perceive
// busy/idle transitions on the main region.
const isFetching = useIsFetching()

// On navigation: announce the new page to assistive tech (polite live region)
// and move focus to <main> so keyboard/SR users are not stranded on a removed
// node. Not immediate, so the initial mount does not steal focus.
watch(
  () => route.fullPath,
  () => {
    routeAnnounce.value = (route.meta.title as string | undefined) ?? 'Honeywatch'
    void nextTick(() => document.getElementById('main')?.focus())
  },
)
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main">Skip to main content</a>
    <div class="visually-hidden" role="status" aria-live="polite">{{ routeAnnounce }}</div>

    <header class="shell-header">
      <div class="shell-header-inner">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">●</span>
          <span class="brand-name">Honeywatch</span>
        </div>

        <nav class="shell-nav" aria-label="Primary">
          <RouterLink to="/" class="nav-link" exact-active-class="nav-link-active">
            Overview
          </RouterLink>
          <RouterLink to="/activity" class="nav-link" active-class="nav-link-active">
            Activity
          </RouterLink>
          <!-- Manual prefix-active so Sessions stays lit on /sessions/:id too. -->
          <RouterLink to="/sessions" class="nav-link" :class="{ 'nav-link-active': sessionsActive }">
            Sessions
          </RouterLink>
        </nav>
      </div>
    </header>

    <main id="main" class="shell-main" tabindex="-1" :aria-busy="isFetching > 0">
      <div class="shell-main-inner">
        <slot />
      </div>
    </main>

    <footer class="shell-footer">
      <div class="shell-footer-inner">
        <div class="credits">
          <div class="credit">
            <span class="credit-name">Piotr Krzysztof Lis</span>
            <span class="credit-links">
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
          </div>

          <div class="credit">
            <span class="credit-name">Jakub Kucharski</span>
            <span class="credit-links">
              <IconLink
                icon="linkedin"
                href="https://www.linkedin.com/in/jakub-kucharski-360811305/"
                label="Jakub on LinkedIn"
              />
              <IconLink
                icon="github"
                href="https://github.com/kubson2002k"
                label="Jakub on GitHub"
              />
            </span>
          </div>
        </div>

        <div class="repo">
          <IconLink
            icon="github"
            href="https://github.com/straightchlorine/honeywatch"
            label="Honeywatch repository on GitHub"
          />
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* dvh tracks the mobile URL bar so the page fits, not 100vh */
  background: var(--bg-0);
  color: var(--text);
  overflow: hidden;
}

.skip-link {
  position: absolute;
  left: var(--space-3);
  top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--accent);
  color: var(--bg-0);
  border-radius: var(--radius-sm);
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

.shell-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: color-mix(in srgb, var(--bg-1) 85%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}

.shell-header-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 700;
  letter-spacing: -0.01em;
  font-size: var(--type-lg);
}

.brand-mark {
  color: var(--accent);
  font-size: var(--type-xl);
  line-height: 1;
}

.brand-name {
  color: var(--text);
}

.shell-nav {
  display: flex;
  gap: var(--space-1);
  flex: 1;
  margin-left: var(--space-4);
}

.nav-link {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  text-decoration: none;
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
  font-weight: 500;
  transition: color var(--motion-fast) ease, background var(--motion-fast) ease;
}

.nav-link:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.nav-link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.nav-link-active {
  color: var(--accent);
  background: var(--surface);
}

.shell-main {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  overflow-y: auto;
}

.shell-main-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-5);
  /* Cap to the viewport so flex:1 children (e.g. the map) shrink to fit and the
     page doesn't scroll on desktop; content that genuinely overflows (short /
     mobile viewports) still scrolls via .shell-main's overflow-y:auto. */
  height: 100%;
  display: flex;
  flex-direction: column;
}

.shell-main:focus-visible {
  outline: none;
}

.shell-footer {
  flex: 0 0 auto;
  border-top: 1px solid var(--border);
  background: var(--bg-1);
}

.shell-footer-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.credits {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-5);
}

.credit {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
}

.credit-name {
  color: var(--text);
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
  font-weight: 500;
}

.credit-links {
  display: inline-flex;
  gap: var(--space-1);
}

.repo {
  display: inline-flex;
  align-items: center;
}

@media (max-width: 768px) {
  .shell-header-inner {
    flex-wrap: wrap;
  }
  .shell-nav {
    order: 3;
    flex-basis: 100%;
    margin-left: 0;
  }
}
</style>
