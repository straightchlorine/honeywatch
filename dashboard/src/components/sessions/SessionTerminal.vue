<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SessionDetailResponse } from '@/api/generated/types.gen'
import { buildTranscript } from './useTerminalTranscript'
import TerminalLine from './TerminalLine.vue'
import { humanizeDuration } from '@/utils/duration'
import { sanitizeAttackerText } from '@/utils/sanitize'

const props = defineProps<{ session: SessionDetailResponse }>()

const lines = computed(() => buildTranscript(props.session))

function field(raw: string): string {
  return sanitizeAttackerText(raw, { mode: 'escape', allowWhitespace: false })
}

const proto = computed(() => field(props.session.protocol).toUpperCase())
const country = computed(() =>
  props.session.country ? field(props.session.country) : 'Unknown origin',
)
const duration = computed(() => humanizeDuration(props.session.started_at, props.session.ended_at))
const startedUtc = computed(() => fmtUtc(props.session.started_at))

const title = computed(() => {
  const parts = ['honeypot', proto.value, country.value]
  if (startedUtc.value) parts.push(startedUtc.value)
  if (duration.value !== '—') parts.push(duration.value)
  return parts.join(' · ')
})

const copied = ref(false)
const termBody = ref<HTMLElement | null>(null)
const canCopy = typeof navigator !== 'undefined' && !!navigator.clipboard

function transcriptText(): string {
  return lines.value
    .map((l) =>
      l.kind === 'command'
        ? `${l.user}@honeypot:~$ ${l.segments.map((s) => s.text).join('')}`
        : `# ${l.text}`,
    )
    .join('\n')
}

async function copyTranscript(): Promise<void> {
  // Without the async clipboard API (insecure context / older browser), degrade
  // to selecting the transcript so the user can still copy with Ctrl/Cmd+C.
  if (!canCopy) {
    selectTranscript()
    return
  }
  try {
    await navigator.clipboard.writeText(transcriptText())
    copied.value = true
    window.setTimeout(() => (copied.value = false), 2000)
  } catch {
    selectTranscript()
  }
}

function selectTranscript(): void {
  const el = termBody.value
  const sel = typeof window !== 'undefined' ? window.getSelection() : null
  if (!el || !sel) return
  const range = document.createRange()
  range.selectNodeContents(el)
  sel.removeAllRanges()
  sel.addRange(range)
}

function fmtUtc(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' })} UTC`
}
</script>

<template>
  <!-- A named <section> implicitly exposes role="region" (no explicit role
       needed); the aria-label gives assistive tech a meaningful landmark name. -->
  <section class="terminal" :aria-label="`Terminal replay — ${proto} session from ${country}`">
    <header class="term-bar">
      <span class="dots" aria-hidden="true"><i /><i /><i /></span>
      <span class="term-title">{{ title }}</span>
      <button type="button" class="copy-btn" @click="copyTranscript">
        {{ copied ? 'Copied' : canCopy ? 'Copy transcript' : 'Select transcript' }}
      </button>
      <span class="visually-hidden" role="status" aria-live="polite">{{
        copied ? 'Transcript copied to clipboard' : ''
      }}</span>
    </header>

    <div
      ref="termBody"
      class="term-body"
      tabindex="0"
      role="group"
      :aria-label="`Session transcript, ${lines.length} lines`"
    >
      <TerminalLine v-for="line in lines" :key="line.id" :line="line" />
    </div>

    <details class="term-note">
      <summary>About this replay</summary>
      <p class="note-body">
        Honeywatch reconstructs this session from captured events. Lines marked ‹…› are annotations,
        not attacker output. IP addresses are redacted; no command output was recorded.
      </p>
    </details>
  </section>
</template>

<style scoped>
.terminal {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-md);
}

.term-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
}

.dots {
  display: inline-flex;
  gap: 6px;
  flex: 0 0 auto;
}

.dots i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border-strong);
}

.dots i:nth-child(1) {
  background: var(--error);
}
.dots i:nth-child(2) {
  background: var(--warning);
}
.dots i:nth-child(3) {
  background: var(--success);
}

.term-title {
  flex: 1 1 auto;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.copy-btn {
  flex: 0 0 auto;
  min-height: var(--control-h);
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-3);
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  cursor: pointer;
  transition:
    background var(--motion-fast) ease,
    border-color var(--motion-fast) ease;
}

.copy-btn:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.copy-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.term-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-3);
  background: var(--bg-0);
}

.term-body:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.term-note {
  flex: 0 0 auto;
  font-size: var(--type-xs);
  line-height: var(--type-xs-lh);
  color: var(--text-muted);
  background: var(--bg-1);
  border-top: 1px solid var(--border);
}

.term-note > summary {
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  list-style: none;
  color: var(--text-dim);
}

.term-note > summary::-webkit-details-marker {
  display: none;
}

.term-note .note-body {
  margin: 0;
  padding: 0 var(--space-3) var(--space-2);
}

/* Desktop: the disclaimer is short enough to always show -- hide the toggle and
   force the body open regardless of the details state. On mobile it stays a
   real <details> (collapsed by default) so it does not eat the terminal hero. */
@media (min-width: 769px) {
  .term-note > summary {
    display: none;
  }
  .term-note .note-body {
    display: block;
    padding-top: var(--space-2);
  }
}
</style>
