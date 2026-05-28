<script setup lang="ts">
  import { computed, onErrorCaptured, ref } from 'vue'

  withDefaults(
    defineProps<{
      fallbackTitle?: string
    }>(),
    { fallbackTitle: 'Something went wrong' },
  )

  const error = ref<Error | null>(null)

  onErrorCaptured((err, _instance, info) => {
    console.error('[ErrorBoundary]', err, info)
    error.value = err instanceof Error ? err : new Error(String(err))
    return false
  })

  // Strip C0/C1 control chars and bidi overrides; truncate to 500 chars.
  const CONTROL_CHARS = new RegExp(
    // eslint-disable-next-line no-control-regex
    '[\\u0000-\\u001f\\u007f-\\u009f\\u200e\\u200f\\u202a-\\u202e\\u2066-\\u2069]',
    'g',
  )

  const safeMessage = computed(() => {
    const raw = error.value?.message ?? ''
    const cleaned = raw.replace(CONTROL_CHARS, '')
    return cleaned.length > 500 ? cleaned.slice(0, 500) + '...' : cleaned
  })

  function reset() {
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
