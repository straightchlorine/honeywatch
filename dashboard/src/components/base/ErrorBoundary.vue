<script setup lang="ts">
  import { computed, onErrorCaptured, ref } from 'vue'
  import { useQueryClient } from '@tanstack/vue-query'
  import { sanitizeAttackerText } from '@/utils/sanitize'

  withDefaults(
    defineProps<{
      fallbackTitle?: string
    }>(),
    { fallbackTitle: 'Something went wrong' },
  )

  const error = ref<Error | null>(null)
  const queryClient = useQueryClient()

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
    return false
  })

  // Strip control chars + bidi overrides from attacker-derived messages and cap
  // length. Shared rule lives in utils/sanitize.
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
</script>

<template>
  <div v-if="error" class="boundary" role="alert">
    <div class="boundary-inner">
      <h4 class="boundary-title">{{ fallbackTitle }}</h4>
      <p class="boundary-message">{{ safeMessage }}</p>
      <button type="button" class="boundary-button" @click="reset">Try again</button>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
  .boundary {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-5);
    color: var(--text);
  }

  .boundary-inner {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .boundary-title {
    margin: 0;
    font-size: var(--type-lg);
    line-height: var(--type-lg-lh);
    font-weight: 600;
    color: var(--error);
  }

  .boundary-message {
    margin: 0;
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    color: var(--text-muted);
    font-family: var(--font-mono);
    word-break: break-word;
  }

  .boundary-button {
    appearance: none;
    background: var(--accent);
    color: var(--bg-0);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-4);
    font-size: var(--type-sm);
    line-height: var(--type-sm-lh);
    font-weight: 600;
    cursor: pointer;
    transition: background var(--motion-fast) ease;
  }

  .boundary-button:hover {
    background: var(--accent-strong);
  }

  .boundary-button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
</style>
