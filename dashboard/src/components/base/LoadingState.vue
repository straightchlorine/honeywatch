<script setup lang="ts">
  /**
   * Suspense fallback while a page loads during in-app navigation: the same turning
   * hexagon as the full-screen loading splash (#hw-splash in index.html), centred. It
   * fades in after 220ms, so quick navigations never show it. On a page change App.vue
   * has already kept the old page up for that long, so `immediate` skips the second wait.
   */
  import HexIcon from './HexIcon.vue'

  defineProps<{ immediate?: boolean }>()
</script>

<template>
  <div class="loading" :class="{ immediate }" role="status">
    <HexIcon :size="36" class="loading-mark" />
    <span class="visually-hidden">Loading</span>
  </div>
</template>

<style scoped>
  .loading {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    pointer-events: none;
    /* tokens.css's reduced-motion rule shortens durations but not delays, so the 220ms
       wait always applies; fill mode "both" keeps the mark invisible until it ends. */
    animation: loading-in 300ms ease 220ms both;
  }
  .loading.immediate {
    animation-delay: 0s;
  }

  /* tokens.css cuts animations to almost nothing for reduced motion. A fade is not
     movement, so keep it rather than pop the mark in (index.html does the same). */
  @media (prefers-reduced-motion: reduce) {
    .loading {
      animation-duration: 300ms !important;
    }
  }

  @media (prefers-reduced-motion: no-preference) {
    /* Same turn as the splash logo (hw-turn in index.html): 60deg with a slight overshoot,
       then a hold. */
    .loading-mark {
      animation: loading-turn 1400ms linear 220ms infinite;
    }
    .immediate .loading-mark {
      animation-delay: 0s;
    }
  }

  @keyframes loading-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @keyframes loading-turn {
    0% {
      transform: rotate(0);
      animation-timing-function: cubic-bezier(0.62, 0, 0.22, 1);
    }
    34% {
      transform: rotate(62.5deg);
      animation-timing-function: cubic-bezier(0.3, 0, 0.3, 1);
    }
    46%,
    100% {
      transform: rotate(60deg);
    }
  }
</style>
