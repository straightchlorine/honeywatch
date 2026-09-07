<script setup lang="ts">
  /**
   * Reuses the same data source as the full replay page (/sessions/:id)
   * to ensure consistency across views.
   */
  import { computed } from 'vue'
  import { useQuery } from '@tanstack/vue-query'
  import { getSessionByIdOptions } from '@/api/generated/@tanstack/vue-query.gen'
  import { buildTranscript } from './useTerminalTranscript'
  import TerminalLine from './TerminalLine.vue'
  import { sanitizeAttackerText } from '@/utils/sanitize'
  import { redactIps } from '@/utils/redactIps'
  import { ICONS } from '@/components/icons'
  import HwBadge from '../base/HwBadge.vue'

  const { sessionId } = defineProps<{ sessionId: string }>()

  const detailQ = useQuery({ ...getSessionByIdOptions({ path: { session_id: sessionId } }) })

  const lines = computed(() => (detailQ.data.value ? buildTranscript(detailQ.data.value) : []))

  function field(raw: string): string {
    return sanitizeAttackerText(raw, { mode: 'escape', allowWhitespace: false })
  }

  const credRows = computed(() => {
    const attempts = detailQ.data.value?.auth_attempts ?? []
    return attempts.map((a) => ({
      key: a.id,
      text: `${field(a.username) || '(blank)'}:${redactIps(field(a.password), undefined, { numericHosts: false }).text || '(blank)'}`,
      ok: a.success,
    }))
  })

  const download = computed(() => detailQ.data.value?.downloads[0] ?? null)
  const clientLine = computed(() => {
    const s = detailQ.data.value
    if (!s) return ''
    return `SSH-2.0-${field(s.protocol).toUpperCase()}`
  })
</script>

<template>
  <div class="detail">
    <div v-if="detailQ.isPending.value" class="loading" role="status">Loading transcript...</div>
    <template v-else-if="detailQ.data.value">
      <div class="term-col">
        <div class="term" role="log" aria-label="Command transcript preview" tabindex="0">
          <TerminalLine v-for="line in lines" :key="line.id" :line="line" />
          <p v-if="!lines.length" class="empty">
            no commands - disconnected right after logging in
          </p>
        </div>
      </div>
      <div class="facts">
        <div class="creds-block">
          <h2>Credentials tried</h2>
          <div class="cred-list" tabindex="0" aria-label="Credentials tried">
            <div
              v-for="c in credRows"
              :key="c.key"
              class="mono cred"
              :class="c.ok ? 'cred-ok' : 'cred-no'"
            >
              {{ c.text }} {{ c.ok ? '(accepted)' : '(rejected)' }}
            </div>
          </div>
        </div>
        <div v-if="download">
          <h2>Files</h2>
          <RouterLink :to="{ name: 'payloads' }" class="mono">
            <HwBadge tone="amber">{{ download.sha256?.slice(0, 16) ?? 'download' }}</HwBadge>
          </RouterLink>
        </div>
        <div>
          <h2>Software used</h2>
          <span class="mono">{{ clientLine }}</span>
        </div>
        <div class="detail-actions">
          <RouterLink
            :to="{ name: 'session-detail', params: { id: sessionId } }"
            class="btn primary"
          >
            Replay
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path :d="ICONS['chevron-right']" />
            </svg>
          </RouterLink>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
  /* Apply cap to both columns (not just .term) to keep .facts and .term aligned
     at the bottom; capping only one would push the action button off-screen. */
  .detail {
    --detail-max: 306px;
    display: grid;
    grid-template-columns: minmax(0, 2.6fr) minmax(0, 1fr);
    gap: 16px;
    box-sizing: border-box;
    padding-top: 14px;
  }

  .loading {
    grid-column: 1 / -1;
    color: var(--text-dim);
    font-size: 12.5px;
  }

  .term-col {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .term {
    flex: 1;
    min-height: 0;
    /* Scrolls past twelve lines instead of pushing rows below further down. */
    max-height: var(--detail-max);
    background: var(--map-ocean);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .term:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  .empty {
    margin: 0;
    color: var(--text-dim);
    font-style: italic;
    font-size: 12.5px;
  }

  .facts {
    display: flex;
    flex-direction: column;
    gap: 10px;
    font-size: 12.5px;
    min-width: 0;
    min-height: 0;
    max-height: var(--detail-max);
  }

  /* Credential list scrolls independently; Files, Software used, and action button stay pinned. */
  .creds-block {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .cred-list {
    min-height: 0;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .cred-list:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .facts h2 {
    margin: 0 0 4px;
    font: 650 10.5px var(--font-sans);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 12px;
  }

  .cred {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .cred-ok {
    color: var(--ok);
  }
  .cred-no {
    color: var(--bad);
  }

  .detail-actions {
    margin-top: auto;
    display: flex;
    gap: 8px;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: var(--radius-md);
    border: 1px solid var(--accent-dim);
    background: none;
    color: var(--accent);
    font: 600 12.5px var(--font-sans);
    cursor: pointer;
  }
  .btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-0);
  }
  .btn.secondary {
    border-color: var(--border-strong);
    color: var(--text-muted);
    font-weight: 550;
  }
  .btn.secondary:hover {
    border-color: var(--accent-dim);
    color: var(--text);
  }
  .btn:hover {
    text-decoration: none;
  }
  .btn svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }
  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
  }
  .icon-btn svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
  }

  @media (max-width: 760px) {
    .detail {
      display: flex;
      flex-direction: column;
      height: auto;
    }

    .term {
      max-height: 200px;
    }
  }
</style>
