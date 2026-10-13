<script setup lang="ts">
  import { computed, onBeforeUnmount, ref, watch } from 'vue'
  import type { SessionDetailResponse, SessionSummaryResponse } from '@/api/generated/types.gen'
  import { buildTranscript } from './useTerminalTranscript'
  import DownloadsChip from './DownloadsChip.vue'
  import ScoreHex from './ScoreHex.vue'
  import TerminalLine from './TerminalLine.vue'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { humanizeDuration } from '@/utils/duration'
  import { fmtUtcStamp } from '@/utils/format'
  import { sanitizeAttackerText } from '@/utils/sanitize'
  import { buildStory } from '@/utils/sessionStory'
  import { ICONS } from '../icons'
  import StoryChip from './StoryChip.vue'

  // `row` is this session's list-page summary (the detail response has no tcpip count); the
  // view passes it only when the list page is cached.
  const props = defineProps<{
    session: SessionDetailResponse
    row?: SessionSummaryResponse
  }>()

  const lines = computed(() => buildTranscript(props.session))
  const nothingTyped = computed(() =>
    lines.value.every((l) => l.kind === 'banner' || l.kind === 'closed'),
  )

  const sid = computed(() => props.session.id.slice(0, 12))
  // Without the list row the pills count the transcript, so compound commands double-count and
  // tcpip is 0.
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
  const startedUtc = computed(() => fmtUtcStamp(props.session.started_at))

  const title = computed(() => {
    const parts = ['honeypot', proto.value, country.value]
    if (startedUtc.value) parts.push(startedUtc.value)
    if (duration.value !== '-') parts.push(duration.value)
    return parts.join(' \u00b7 ')
  })

  const flag = computed(() => useCountryFlag(props.session.country_code))

  const noteOpen = ref(false)
  const noteBtn = ref<HTMLButtonElement | null>(null)
  function closeNote(): void {
    noteOpen.value = false
    noteBtn.value?.focus()
  }
  function onDocKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') closeNote()
  }
  watch(noteOpen, (open) => {
    if (open) document.addEventListener('keydown', onDocKey)
    else document.removeEventListener('keydown', onDocKey)
  })
  onBeforeUnmount(() => document.removeEventListener('keydown', onDocKey))

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

  const copyLabel = computed(() =>
    copied.value ? 'Copied' : canCopy ? 'Copy transcript' : 'Select transcript',
  )

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
</script>

<template>
  <section class="terminal" :aria-label="`Replay of the ${proto} session from ${country}`">
    <header class="term-bar">
      <span class="dots" aria-hidden="true"><i /><i /><i /></span>
      <span class="term-title">{{ title }}</span>
      <span class="term-tags">
        <ScoreHex v-if="session.max_interest" :interest="session.interest" :ceiling="session.max_interest" />
        <span class="sid">{{ sid }}</span>
        <template v-for="(b, i) in story" :key="i">
          <DownloadsChip
            v-if="b.icon === 'file'"
            :downloads="session.downloads"
            :label="b.label"
            :title="b.title"
          />
          <StoryChip v-else :tone="b.tone" :icon="b.icon" :glyph="b.glyph" :title="b.title" :aria-label="b.title">
            {{ b.label }}
          </StoryChip>
        </template>
      </span>
      <span class="term-meta">
        <span class="term-flag" role="img" :aria-label="country" :title="country">{{ flag }}</span>
        <span>{{ proto }}</span>
        <span v-if="startedUtc">{{ startedUtc }}</span>
        <span v-if="duration !== '-'">{{ duration }}</span>
      </span>
      <button
        type="button"
        class="copy-btn"
        :aria-label="copyLabel"
        :title="copyLabel"
        @click="copyTranscript"
      >
        <svg class="copy-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path :d="copied ? ICONS.check : ICONS.copy" />
        </svg>
      </button>
      <button
        ref="noteBtn"
        type="button"
        class="note-btn"
        aria-label="About this replay"
        aria-controls="replay-note"
        :aria-expanded="noteOpen"
        @click="noteOpen = !noteOpen"
      >
        ?
      </button>
      <span class="visually-hidden" role="status" aria-live="polite">{{
        copied ? 'Transcript copied to clipboard' : ''
      }}</span>
    </header>

    <p v-if="noteOpen" id="replay-note" class="term-note">
      Rebuilt from what the honeypot recorded. Lines in &lt;...&gt; are our notes, not the attacker's. Highlighted text is what they typed to log in. Addresses are hidden, and the honeypot's replies were not recorded.
    </p>

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
    position: relative;
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
    justify-content: center;
    min-width: var(--control-h);
    min-height: var(--control-h);
    padding: 5px;
    background: transparent;
    color: var(--text-muted);
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: color var(--motion-fast) ease;
  }

  .copy-icon {
    display: block;
    width: 0.9rem;
    height: 0.9rem;
    fill: currentColor;
  }

  .copy-btn:hover {
    color: var(--text);
  }

  .copy-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .term-body {
    flex: 1 1 auto;
    /* Floor so a short transcript does not collapse to a sliver. */
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
    margin: 0;
    padding: var(--space-2) var(--space-3);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
    background: var(--bg-1);
    border-bottom: 1px solid var(--border);
  }

  .note-btn {
    flex: 0 0 auto;
    min-width: var(--control-h);
    min-height: var(--control-h);
    padding: 0;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: var(--type-sm, 14px);
    font-weight: 700;
    cursor: pointer;
  }

  .note-btn:hover,
  .note-btn[aria-expanded='true'] {
    color: var(--text);
    background: var(--surface-hover);
  }

  .note-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  @media (max-width: 768px) {
    .term-bar {
      order: -2;
      flex-wrap: wrap;
      align-items: center;
      row-gap: var(--space-1);
    }
    .term-title {
      display: none;
    }
    /* Narrower clock gutter (width is in ch of the shrunken font) so lines wrap less. */
    .term-body :deep(.ts) {
      font-size: 0.8em;
    }
    .copy-btn {
      order: 2;
      margin-left: auto;
    }
    .note-btn {
      order: 2;
    }
    .term-tags {
      order: 3;
      flex-basis: 100%;
    }
    .term-meta {
      order: 4;
      flex-basis: 100%;
      display: flex;
      align-items: baseline;
      gap: var(--space-2);
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      font-family: var(--font-mono);
      font-size: var(--type-xs);
      line-height: var(--type-xs-lh);
      color: var(--text-muted);
    }
    .term-meta > span + span::before {
      content: '\00b7';
      margin-right: var(--space-2);
    }
    .term-flag {
      flex: 0 0 24px;
      text-align: center;
    }
    .term-meta > .term-flag + span::before {
      content: none;
    }
  }
</style>
