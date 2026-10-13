<script setup lang="ts">
  import { computed, nextTick, onErrorCaptured, ref, useTemplateRef } from 'vue'
  import { useRouter } from 'vue-router'
  import { useQueryClient } from '@tanstack/vue-query'
  import { sanitizeAttackerText } from '@/utils/sanitize'
  import { hexPoints } from '@/utils/hex'
  import { exitSplash } from '@/utils/splash'

  withDefaults(
    defineProps<{
      fallbackTitle?: string
    }>(),
    { fallbackTitle: 'Something went wrong' },
  )

  const error = ref<Error | null>(null)
  const queryClient = useQueryClient()
  const router = useRouter()
  const retryBtn = useTemplateRef<HTMLButtonElement>('retry')
  const HEX = hexPoints(10, 11, 9)
  const ECHO = hexPoints(10, 11, 14.5)

  // The generated client throws the API error envelope (a plain object with a
  // string `message`), not an Error, so unwrap it instead of rendering
  // "[object Object]".
  function toError(err: unknown): Error {
    if (err instanceof Error) return err
    if (err && typeof err === 'object') {
      const message = (err as { message?: unknown }).message
      if (typeof message === 'string' && message) return new Error(message)
      try {
        return new Error(JSON.stringify(err))
      } catch {
        return new Error('Unknown error')
      }
    }
    return new Error(String(err))
  }

  onErrorCaptured((err, _instance, info) => {
    if (import.meta.env.DEV) console.error('[ErrorBoundary]', err, info)
    error.value = toError(err)
    // Showing this alert removes the Suspense below, so nothing else would tell the
    // loading splash to leave, and the splash would stay on top of the alert.
    exitSplash()
    // The alert replaces the whole app, nav included, so focus would fall to <body>.
    void nextTick(() => retryBtn.value?.focus({ preventScroll: true }))
    return false
  })

  // Strip control chars + bidi overrides from attacker-derived messages and cap
  // length.
  const safeMessage = computed(() => {
    const cleaned = sanitizeAttackerText(error.value?.message ?? '', {
      mode: 'strip',
      allowWhitespace: false,
    })
    return cleaned.length > 500 ? cleaned.slice(0, 500) + '...' : cleaned
  })

  function reset() {
    // Reset cached query state so a re-render actually refetches instead of
    // immediately re-throwing the cached rejection.
    void queryClient.resetQueries()
    error.value = null
  }

  // Modified and non-primary clicks keep the browser's own behaviour (new tab, new window).
  function goHome(e: MouseEvent) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
      return
    e.preventDefault()
    // Navigate first: resetting while still on the failing route would load it once more.
    // If the route chunk fails to load, a hard navigation fetches the chunks again.
    void router.push('/').then(reset, () => window.location.assign('/'))
  }
</script>

<template>
  <div v-if="error" class="boundary" role="alert">
    <div class="boundary-inner">
      <svg class="boundary-mark" viewBox="0 0 20 22" aria-hidden="true">
        <polygon class="boundary-echo" :points="ECHO" />
        <polygon class="boundary-hex" :points="HEX" />
        <path class="boundary-bang" d="M10 6.6V11.6" />
        <circle class="boundary-dot" cx="10" cy="15" r="1.15" />
      </svg>
      <h1 class="boundary-title">{{ fallbackTitle }}</h1>
      <p class="boundary-message">{{ safeMessage }}</p>
      <div class="boundary-actions">
        <button ref="retry" type="button" class="boundary-button" @click="reset">Try again</button>
        <a class="boundary-link" href="/" @click="goHome">Back to overview</a>
      </div>
    </div>
  </div>
  <!-- Suspense mounts its fallback when its timeout fires even if it was unmounted first, so
       an error inside that wait would leave the page loader spinning over this alert. Inside
       this wrapper the late loader lands in a detached element instead. -->
  <div v-else class="boundary-host"><slot /></div>
</template>

<style scoped>
  .boundary-host {
    display: contents;
  }

  .boundary {
    /* Outside .shell, so it carries the 4K zoom itself; 100dvh is scaled by it, divide back. */
    zoom: var(--ui-zoom, 1);
    min-height: calc(100dvh / var(--ui-zoom, 1));
    display: grid;
    place-items: center;
    padding: var(--space-5) var(--space-4);
    background:
      radial-gradient(
        circle 45vmin at 50% 50%,
        color-mix(in srgb, var(--error) 8%, transparent),
        transparent
      ),
      var(--bg-0);
    color: var(--text);
  }

  .boundary-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    max-width: 480px;
    text-align: center;
  }

  /* Same hexagon as the loading splash, with the centre dot turned into an exclamation mark. */
  .boundary-mark {
    width: 88px;
    height: 97px;
    margin-bottom: var(--space-2);
    overflow: visible;
    animation: boundary-in 480ms cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }

  .boundary-hex,
  .boundary-bang {
    fill: none;
    stroke: var(--error);
    stroke-width: 1.6;
  }

  .boundary-bang {
    stroke-width: 1.8;
    stroke-linecap: round;
  }

  .boundary-dot {
    fill: var(--error);
  }

  .boundary-echo {
    fill: none;
    stroke: var(--error);
    stroke-width: 1px;
    vector-effect: non-scaling-stroke;
    opacity: 0.28;
    transform-origin: 10px 11px;
    transform: rotate(30deg);
  }

  .boundary-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: var(--type-xl);
    line-height: var(--type-xl-lh);
    font-weight: 700;
    color: var(--text);
    text-wrap: balance;
  }

  .boundary-message {
    margin: 0;
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    color: var(--text-muted);
    font-family: var(--font-mono);
    word-break: break-word;
  }

  .boundary-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: var(--space-3) var(--space-5);
    margin-top: var(--space-3);
  }

  .boundary-button {
    appearance: none;
    font-family: inherit;
    background: var(--accent);
    color: var(--bg-0);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-5);
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    font-weight: 600;
    cursor: pointer;
    transition: background var(--motion-fast) ease;
  }

  .boundary-button:hover {
    background: var(--accent-strong);
  }

  .boundary-link {
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    color: var(--text-muted);
    text-decoration: underline;
    text-underline-offset: 3px;
    transition: color var(--motion-fast) ease;
  }

  .boundary-link:hover {
    color: var(--accent);
  }

  .boundary-button:focus-visible,
  .boundary-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  @media (pointer: coarse) {
    .boundary-button,
    .boundary-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
    }
  }

  @media (max-width: 640px) {
    .boundary-mark {
      width: 64px;
      height: 70px;
    }

    .boundary-actions {
      flex-direction: column;
      align-self: stretch;
    }

    .boundary-button {
      align-self: stretch;
    }
  }

  @keyframes boundary-in {
    from {
      opacity: 0;
      transform: scale(0.88);
    }
  }
</style>
