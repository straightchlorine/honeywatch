<script setup lang="ts">
  import { computed } from 'vue'

  type Status = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

  const props = defineProps<{
    status: Status
  }>()

  const LABELS: Record<Status, string> = {
    idle: 'Idle',
    connecting: 'Connecting',
    open: 'Live',
    reconnecting: 'Reconnecting',
    closed: 'Offline',
  }

  const TITLES: Record<Status, string> = {
    idle: 'Connection idle',
    connecting: 'Establishing connection',
    open: 'Live stream connected',
    reconnecting: 'Reconnecting to live stream',
    closed: 'Live stream disconnected',
  }

  const label = computed(() => LABELS[props.status])
  const title = computed(() => TITLES[props.status])
  const statusClass = computed(() => `status-${props.status}`)
</script>

<template>
  <span
    class="pill"
    :class="statusClass"
    role="status"
    aria-live="polite"
    :title="title"
    :aria-label="title"
  >
    <span class="dot" aria-hidden="true" />
    <span class="label">{{ label }}</span>
  </span>
</template>

<style scoped>
  .pill {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-3);
    border-radius: 999px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-dim);
    flex-shrink: 0;
  }

  .status-idle .dot {
    background: var(--text-dim);
  }

  .status-connecting .dot {
    background: var(--warning);
    animation: pulse 1200ms ease-in-out infinite;
  }

  .status-open .dot {
    background: var(--success);
    box-shadow: 0 0 8px rgba(132, 204, 22, 0.6);
  }

  .status-open {
    color: var(--text);
    border-color: var(--border-strong);
  }

  .status-reconnecting .dot {
    background: var(--warning);
    animation: pulse 800ms ease-in-out infinite;
  }

  .status-closed .dot {
    background: var(--error);
  }

  .status-closed {
    color: var(--text-muted);
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.35;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dot {
      animation: none !important;
    }
  }
</style>
