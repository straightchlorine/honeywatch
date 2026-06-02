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
          <RouterLink to="/credentials" class="nav-link" active-class="nav-link-active">
            Credentials
          </RouterLink>
          <!-- Manual prefix-active so Sessions stays lit on /sessions/:id too. -->
          <RouterLink
            to="/sessions"
            class="nav-link"
            :class="{ 'nav-link-active': sessionsActive }"
          >
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
          <!-- Mobile-only wordmark: the brand moves out of the (tight) header
               down here to reclaim top space. aria-hidden -- the repo IconLink's
               own label names the project for assistive tech. -->
          <span class="footer-brand" aria-hidden="true">
            <span class="footer-dot">●</span> Honeywatch
          </span>
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
    transition:
      color var(--motion-fast) ease,
      background var(--motion-fast) ease;
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
    /* Always reserve the scrollbar gutter so content width doesn't shift when a
       page's height crosses the viewport (e.g. switching the Credentials hero
       between a full 8-row list and a 1-row Usernames view). */
    scrollbar-gutter: stable;
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
    gap: var(--space-2);
  }

  /* Mobile-only footer wordmark (desktop keeps the contributor credits). */
  .footer-brand {
    display: none;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    font-weight: 700;
    color: var(--text);
  }
  .footer-dot {
    color: var(--accent);
  }

  @media (max-width: 768px) {
    /* The page already scrolls on mobile (the scrollbar is always present, so no
       width jitter to guard against). Drop the reserved gutter here -- on mobile
       it just insets the content on the right and makes the cards look
       off-centre. */
    .shell-main {
      scrollbar-gutter: auto;
    }
    .shell-header-inner {
      flex-wrap: wrap;
    }
    /* Drop the brand from the header on mobile -- it reappears in the footer
       below -- so the header collapses to just the nav row and gives the page
       back a row of top space. */
    .brand {
      display: none;
    }
    .shell-nav {
      order: 3;
      flex-basis: 100%;
      margin-left: 0;
    }

    /* Drop the contributor credits; the footer becomes "● Honeywatch + GitHub". */
    .credits {
      display: none;
    }
    .shell-footer-inner {
      justify-content: center;
    }
    .footer-brand {
      display: inline-flex;
    }
  }
</style>
