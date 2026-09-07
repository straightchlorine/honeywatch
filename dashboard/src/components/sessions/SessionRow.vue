<script setup lang="ts">
  import { computed, ref } from 'vue'
  import type { SessionSummaryResponse } from '@/api/generated/types.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { seq } from '@/composables/useSeqScale'
  import { hexPoints } from '@/utils/hex'
  import { fmtRelativeTime } from '@/utils/format'
  import { humanizeDuration } from '@/utils/duration'
  import { buildStory, scoreFrac } from '@/utils/sessionStory'
  import { ICONS } from '@/components/icons'
  import HwBadge from '../base/HwBadge.vue'
  import SessionExpansion from './SessionExpansion.vue'

  const { row, expanded, maxInterest } = defineProps<{
    row: SessionSummaryResponse
    expanded: boolean
    maxInterest: number
  }>()
  const emit = defineEmits<{ toggle: [] }>()

  const story = computed(() => buildStory(row))
  const frac = computed(() => scoreFrac(row.interest, maxInterest))
  // Tuned thresholds: glow starts at 60% of the top score; below interest=5
  // there's too little activity to color, so the hex stays neutral grey.
  const hot = computed(() => frac.value > 0.6)
  const hexFill = computed(() => (row.interest > 5 ? seq(Math.pow(frac.value, 0.9)) : 'var(--surface-2)'))
  // Normalized 0-100: hottest session reads as 100, others scale beneath it.
  const displayScore = computed(() => Math.round((100 * row.interest) / Math.max(1, maxInterest)))
  const points = hexPoints(15, 16.5, 14)

  const flag = computed(() => useCountryFlag(row.country_code))
  // Fallback chain: country name -> code -> "Unknown"; never a bare underscore or empty cell.
  const countryText = computed(() => row.country ?? row.country_code ?? 'Unknown')
  // City is dropped when the API has none, or when it duplicates the country
  // name (Singapore) - never "Singapore, Singapore".
  const cityText = computed(() => {
    const city = row.city?.trim()
    if (!city) return null
    return city.toLowerCase() === countryText.value.trim().toLowerCase() ? null : city
  })
  const originFull = computed(() => (cityText.value ? `${countryText.value}, ${cityText.value}` : countryText.value))
  const duration = computed(() => humanizeDuration(row.started_at, row.ended_at))
  const started = computed(() => (row.started_at ? fmtRelativeTime(row.started_at) : '-'))

  // Prose accessibility: visible 12-char id is visual only, not read by screen readers.
  const ariaLabel = computed(
    () => `Session from ${originFull.value}, interest score ${displayScore.value} of 100, lasting ${duration.value}`,
  )

  const copied = ref(false)
  const canCopy = typeof navigator !== 'undefined' && !!navigator.clipboard

  async function copyId(): Promise<void> {
    if (!canCopy) return
    try {
      await navigator.clipboard.writeText(row.id)
      copied.value = true
      window.setTimeout(() => (copied.value = false), 2000)
    } catch {
      // Clipboard write may be denied; button remains un-copied.
    }
  }

  const tooltip = useHwTooltip()

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      emit('toggle')
    }
  }
</script>

<template>
  <!-- eslint-disable vuejs-accessibility/click-events-have-key-events -->
  <tr
    class="srow"
    :class="{ quiet: row.interest < 4 }"
    tabindex="0"
    :aria-expanded="expanded"
    :aria-label="ariaLabel"
    @click="emit('toggle')"
    @keydown="onKeydown"
  >
    <td class="session">
      <span class="chevron" :class="{ rotated: expanded }" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="14" height="14">
          <path :d="ICONS['chevron-right']" fill="currentColor" />
        </svg>
      </span>
      <button
        type="button"
        class="score-hex"
        :class="{ hot }"
        :aria-label="`Interest score ${displayScore} of 100`"
        @pointerenter="tooltip.show('Interest score - higher when a session ran commands, dropped files, got control or tried to relay')"
        @pointermove="tooltip.move($event as PointerEvent)"
        @pointerleave="tooltip.hide()"
        @focus="tooltip.show('Interest score - higher when a session ran commands, dropped files, got control or tried to relay')"
        @blur="tooltip.hide()"
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
      </button>
      <span class="sid-wrap">
        <span class="sid">{{ row.id.slice(0, 12) }}</span>
        <button
          v-if="canCopy"
          type="button"
          class="sid-copy"
          :class="{ done: copied }"
          :aria-label="copied ? 'Session id copied' : `Copy session id ${row.id}`"
          @click.stop="copyId"
          @keydown.enter.stop
          @keydown.space.stop
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path :d="copied ? ICONS.check : ICONS.copy" />
          </svg>
        </button>
      </span>
    </td>
    <td class="story">
      <span class="badges">
        <HwBadge v-for="(b, i) in story" :key="i" :tone="b.tone" :title="b.title">
          {{ b.label }}
        </HwBadge>
      </span>
    </td>
    <td class="origin">
      <span class="flag" aria-hidden="true">{{ flag }}</span>
      <span class="country">{{ countryText }}</span>
      <template v-if="cityText">
        <span class="dot" aria-hidden="true">&middot;</span>
        <span class="city">{{ cityText }}</span>
      </template>
    </td>
    <td class="spacer"></td>
    <td class="r num duration">{{ duration }}</td>
    <td class="r dim small started">{{ started }}</td>
  </tr>
  <!-- eslint-enable vuejs-accessibility/click-events-have-key-events -->
  <tr class="expand" :hidden="!expanded">
    <td colspan="6">
      <SessionExpansion v-if="expanded" :session-id="row.id" />
    </td>
  </tr>
</template>

<style scoped>
  .srow {
    cursor: pointer;
  }

  /* !important overrides parent table's :deep(td) default (plain-tag selector
     outranks scoped class). */
  .session {
    padding: 3px 10px 3px 16px !important;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .chevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex: 0 0 auto;
    color: var(--text-muted);
    transition: transform var(--motion-fast);
  }

  .chevron.rotated {
    transform: rotate(90deg);
  }

  .srow .sid {
    font-family: var(--font-mono);
    font-size: 12.5px;
    color: var(--accent);
  }

  .srow.quiet td {
    color: var(--text-dim);
  }

  .srow.quiet .sid {
    color: var(--accent-dim);
  }

  .sid-wrap {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  .sid-copy {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    padding: 0;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-dim);
    cursor: pointer;
    /* Hidden, not absent: opacity keeps it in the tab order and stops the id
       from shifting sideways when it appears. */
    opacity: 0;
    transition:
      opacity 120ms ease,
      color 120ms ease;
  }
  .srow:hover .sid-copy,
  .srow:focus-within .sid-copy,
  .sid-copy:focus-visible {
    opacity: 1;
  }
  .sid-copy:hover {
    color: var(--accent);
    background: var(--surface-hover);
  }
  .sid-copy.done {
    opacity: 1;
    color: var(--ok);
  }
  .sid-copy svg {
    width: 13px;
    height: 13px;
    fill: currentColor;
  }

  /* Coarse pointers have no hover, so the control would be unreachable. */
  @media (hover: none) {
    .sid-copy {
      opacity: 1;
    }
  }

  .srow[aria-expanded='true'] {
    background: var(--surface-hover);
  }

  .srow:focus {
    outline: none;
  }

  .srow:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: -2px;
  }

  .score-hex {
    appearance: none;
    padding: 0;
    border: none;
    background: transparent;
    font: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    position: relative;
    width: 26px;
    height: 29px;
    flex: 0 0 auto;
  }

  .score-hex:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 1px;
    border-radius: var(--radius-sm);
  }

  .score-hex svg {
    position: absolute;
    inset: 0;
  }

  .score-hex b {
    position: relative;
    font: 650 10px var(--font-mono);
    color: var(--text);
  }

  .score-hex.hot b {
    color: var(--bg-0);
  }

  .story {
    padding: 3px 10px !important;
  }

  .story .badges {
    display: inline-flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .origin {
    padding: 3px 10px !important;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .origin .flag {
    font-size: 14px;
    flex: 0 0 auto;
  }

  .origin .country,
  .origin .city {
    flex: 0 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .origin .country {
    color: var(--text-muted);
    font-size: 12px;
  }

  .origin .dot {
    flex: 0 0 auto;
    color: color-mix(in srgb, var(--text-dim) 55%, transparent);
    font-size: 12px;
  }

  .origin .city {
    color: var(--text-dim);
    font-size: 12px;
  }

  .dim {
    color: var(--text-dim);
  }

  .small {
    font-size: 11.5px;
  }

  .duration {
    padding: 3px 10px !important;
    text-align: right;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 13px;
  }

  /* Right padding ~22px so the table-scroll region's scrollbar doesn't sit
     directly on top of the text. */
  .started {
    padding: 3px 22px 3px 10px !important;
    text-align: right;
  }

  .spacer {
    padding: 3px 0 !important;
  }

  .expand > td {
    padding: 0 16px 16px;
    background: var(--bg-1);
    border-bottom: 1px solid var(--border-strong);
  }

  @media (max-width: 760px) {
    /* Hide origin/duration/started on mobile (shown in expansion instead).
       Child combinator ensures :nth-child(n+3) targets row cells only. */
    .srow > td:nth-child(n + 3) {
      display: none;
    }
  }
</style>
