<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
  import type { SessionDetailResponse, SessionSummaryResponse } from '@/api/generated/types.gen'
  import { buildTranscript } from './useTerminalTranscript'
  import TerminalLine from './TerminalLine.vue'
  import { humanizeDuration } from '@/utils/duration'
  import { sanitizeAttackerText } from '@/utils/sanitize'
  import { seq } from '@/composables/useSeqScale'
  import { hexPoints } from '@/utils/hex'
  import { buildStory, scoreFrac } from '@/utils/sessionStory'
  import { ICONS } from '../icons'
  import HwBadge from '../base/HwBadge.vue'

  // `row` is this session's list-page summary (the detail response has no interest score or
  // tcpip count); the view passes it only when the list page is cached.
  const props = defineProps<{
    session: SessionDetailResponse
    row?: SessionSummaryResponse
    maxInterest?: number
  }>()

  const lines = computed(() => buildTranscript(props.session))
  const nothingTyped = computed(() =>
    lines.value.every((l) => l.kind === 'banner' || l.kind === 'closed'),
  )

  const sid = computed(() => props.session.id.slice(0, 12))
  // ponytail: without the list row, pills count the transcript (compound commands double-count)
  // and tcpip reads 0; the hex needs the dataset max, so it shows only with the row.
  const story = computed(() =>
    buildStory(
      props.row ?? {
        n_commands: props.session.commands.length,
        n_downloads: props.session.downloads.length,
        n_tcpip: 0,
        auth_success: props.session.auth_attempts.some((a) => a.success),
      },
    ),
  )
  const frac = computed(() => scoreFrac(props.row?.interest ?? 0, props.maxInterest ?? 0))
  const hexFill = computed(() =>
    (props.row?.interest ?? 0) > 5 ? seq(Math.pow(frac.value, 0.9)) : 'var(--surface-2)',
  )
  const displayScore = computed(() => Math.round(100 * frac.value))
  const points = hexPoints(15, 16.5, 14)

  function field(raw: string): string {
    return sanitizeAttackerText(raw, { mode: 'escape', allowWhitespace: false })
  }

  const proto = computed(() => field(props.session.protocol).toUpperCase())
  const country = computed(() =>
    props.session.country ? field(props.session.country) : 'Unknown origin',
  )
  const duration = computed(() =>
    humanizeDuration(props.session.started_at, props.session.ended_at),
  )
  const startedUtc = computed(() => fmtUtc(props.session.started_at))

  const title = computed(() => {
    const parts = ['honeypot', proto.value, country.value]
    if (startedUtc.value) parts.push(startedUtc.value)
    if (duration.value !== '-') parts.push(duration.value)
    return parts.join(' - ')
  })

  const idLine = computed(() => ['honeypot', proto.value, country.value].join(' - '))
  const timeLine = computed(() => {
    const parts: string[] = []
    if (startedUtc.value) parts.push(startedUtc.value)
    if (duration.value !== '-') parts.push(duration.value)
    return parts.join(' - ')
  })

  // Desktop shows the note always (summary hidden), so a closed <details> must be open there.
  const noteOpen = ref(false)
  let noteMq: MediaQueryList | null = null
  const syncNote = () => {
    if (noteMq?.matches) noteOpen.value = true
  }
  onMounted(() => {
    noteMq = window.matchMedia('(min-width: 769px)')
    syncNote()
    noteMq.addEventListener('change', syncNote)
  })
  onBeforeUnmount(() => noteMq?.removeEventListener('change', syncNote))

  const copied = ref(false)
  const termBody = ref<HTMLElement | null>(null)
  const canCopy = typeof navigator !== 'undefined' && !!navigator.clipboard

  function transcriptText(): string {
    return lines.value
      .map((l) => {
        const at = l.time ? `${l.time}  ` : ''
        if (l.kind === 'command') {
          return `${at}${l.user}@honeypot:~$ ${l.segments.map((s) => s.text).join('')}`
        }
        // Auth lines carry the credential as pre/password/post, not a flat string;
        // re-assemble it so the copied transcript matches what is on screen.
        if (l.kind === 'auth-ok' || l.kind === 'auth-fail') {
          return `${at}# ${l.pre}${l.password || '(blank)'}${l.post}`
        }
        return `${at}# ${l.text}`
      })
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
  <section class="terminal" :aria-label="`Replay of the ${proto} session from ${country}`">
    <header class="term-bar">
      <span class="dots" aria-hidden="true"><i /><i /><i /></span>
      <span class="term-title">{{ title }}</span>
      <span class="term-tags">
        <span
          v-if="row && maxInterest"
          class="score-hex"
          :class="{ hot: frac > 0.6 }"
          role="img"
          :aria-label="`Interest score ${displayScore} of 100`"
        >
          <svg viewBox="0 0 30 33" aria-hidden="true">
            <polygon
              :points="points"
              :fill="hexFill"
              stroke="var(--border-strong)"
              :stroke-width="row.interest > 5 ? 0 : 1"
            />
          </svg>
          <b aria-hidden="true">{{ displayScore }}</b>
        </span>
        <span class="sid">{{ sid }}</span>
        <HwBadge v-for="(b, i) in story" :key="i" :tone="b.tone" :title="b.title" :aria-label="b.title">
          {{ b.label }}
          <svg v-if="b.icon" class="badge-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path :d="ICONS[b.icon]" />
          </svg>
        </HwBadge>
      </span>
      <span class="term-meta">
        <span class="term-id">{{ idLine }}</span>
        <span v-if="timeLine" class="term-time">{{ timeLine }}</span>
      </span>
      <button
        type="button"
        class="copy-btn"
        :aria-label="canCopy ? 'Copy transcript' : 'Select transcript'"
        @click="copyTranscript"
      >
        <svg class="copy-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path :d="copied ? ICONS.check : ICONS.copy" />
        </svg>
        <span class="copy-label">{{
          copied ? 'Copied' : canCopy ? 'Copy transcript' : 'Select transcript'
        }}</span>
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
      <p v-if="nothingTyped" class="term-empty">Nothing typed in this session.</p>
    </div>

    <details class="term-note" :open="noteOpen">
      <summary>About this replay</summary>
      <p class="note-body">
        Rebuilt from what the honeypot recorded. Lines in &lt;...&gt; are our notes, not the attacker's. Highlighted text is what they typed to log in. Addresses are hidden, and the honeypot's replies were not recorded.
      </p>
    </details>
  </section>
</template>

<style scoped>
  .terminal {
    display: flex;
    flex-direction: column;
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

  .term-meta {
    display: none;
  }

  .term-tags {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
  }

  .sid {
    font-family: var(--font-mono);
    font-size: 12.5px;
    color: var(--accent);
  }

  .score-hex {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 26px;
  }

  .score-hex svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .score-hex b {
    position: relative;
    font: 700 10px var(--font-mono);
    color: var(--text);
  }

  .score-hex.hot b {
    color: var(--bg-0);
  }

  .badge-icon {
    width: 11px;
    height: 11px;
    fill: currentColor;
  }

  .term-empty {
    margin: 0;
    color: var(--text-dim);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
  }

  .copy-btn {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
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

  .copy-icon {
    display: none;
    width: 1rem;
    height: 1rem;
    fill: currentColor;
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
    /* About six lines; a short transcript no longer stretches to the viewport. */
    min-height: 9rem;
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

  .term-note > summary {
    display: flex;
    align-items: center;
    min-height: var(--control-h);
  }

  .term-note > summary::-webkit-details-marker {
    display: none;
  }

  .term-note .note-body {
    margin: 0;
    padding: 0 var(--space-3) var(--space-2);
  }

  /* Desktop always shows the note; mobile keeps it collapsible to preserve space. */
  @media (min-width: 769px) {
    .term-note > summary {
      display: none;
    }
    .term-note .note-body {
      display: block;
      padding-top: var(--space-2);
    }
  }

  @media (max-width: 768px) {
    .term-bar {
      flex-wrap: wrap;
      align-items: center;
      row-gap: var(--space-1);
    }
    .term-title {
      display: none;
    }
    .copy-btn {
      order: 2;
      margin-left: auto;
      /* Icon only; full control-size tap target. */
      min-width: var(--control-h);
      justify-content: center;
      padding: 5px;
      background: transparent;
      border-color: transparent;
      color: var(--text-muted);
    }
    .copy-btn:hover {
      background: transparent;
      border-color: transparent;
      color: var(--text);
    }
    .copy-icon {
      display: block;
      width: 0.9rem;
      height: 0.9rem;
    }
    .copy-label {
      display: none;
    }
    .term-tags {
      order: 3;
      flex-basis: 100%;
    }
    .term-meta {
      order: 4;
      flex-basis: 100%;
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
      font-family: var(--font-mono);
      font-size: var(--type-xs);
      line-height: var(--type-xs-lh);
      color: var(--text-muted);
    }
    .term-id,
    .term-time {
      white-space: normal;
      overflow-wrap: anywhere;
    }
  }
</style>
