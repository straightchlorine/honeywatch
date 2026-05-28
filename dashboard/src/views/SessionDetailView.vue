<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { getSessionByIdOptions } from '@/api/queries'
import PageHeader from '@/components/base/PageHeader.vue'

const route = useRoute()
const sessionId = computed(() => String(route.params.id ?? ''))

const detail = useQuery(
  computed(() => getSessionByIdOptions({ path: { session_id: sessionId.value } })),
)

await detail.suspense()

const MAX_PAYLOAD_BYTES = 256 * 1024

// Strip C0 controls (except \t \n \r), DEL, C1 controls, and Unicode bidi
// overrides that could spoof rendering of attacker-controlled JSON.
// Built from a code-point predicate to avoid literal control chars in source.
function sanitizePayload(raw: string): string {
  let out = ''
  for (let i = 0; i < raw.length; i++) {
    const code = raw.charCodeAt(i)
    const isAllowedWhitespace = code === 0x09 || code === 0x0a || code === 0x0d
    const isC0 = code <= 0x1f && !isAllowedWhitespace
    const isDelOrC1 = code >= 0x7f && code <= 0x9f
    const isBidiOverride =
      (code >= 0x202a && code <= 0x202e) || (code >= 0x2066 && code <= 0x2069)
    if (isC0 || isDelOrC1 || isBidiOverride) {
      out += '\\x' + code.toString(16).padStart(2, '0').toUpperCase()
    } else {
      out += raw[i]
    }
  }
  return out
}

const payloadText = computed(() => {
  let raw: string
  try {
    raw = JSON.stringify(detail.data.value, null, 2) ?? 'null'
  } catch (err) {
    return `[unable to render session JSON: ${(err as Error).message}]`
  }
  const sanitized = sanitizePayload(raw)
  if (sanitized.length > MAX_PAYLOAD_BYTES) {
    return `${sanitized.slice(0, MAX_PAYLOAD_BYTES)}\n... [truncated]`
  }
  return sanitized
})
</script>

<template>
  <div class="session-detail">
    <PageHeader :title="`Session ${sessionId}`" />

    <pre
      class="payload"
      tabindex="0"
      role="region"
      aria-label="Session JSON payload"
    >{{ payloadText }}</pre>
  </div>
</template>

<style scoped>
.session-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.payload {
  background: var(--bg-2);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  overflow: auto;
  margin: 0;
}

.payload:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
