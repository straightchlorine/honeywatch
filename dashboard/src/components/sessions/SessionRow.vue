<script setup lang="ts">
  import { computed, ref } from 'vue'
  import type { SessionSummaryResponse } from '@/api/generated/types.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { fmtRelativeTime } from '@/utils/format'
  import { humanizeDuration } from '@/utils/duration'
  import { buildStory, scoreFrac } from '@/utils/sessionStory'
  import { ICONS } from '@/components/icons'
  import HwBadge from '../base/HwBadge.vue'
  import ScoreHex from './ScoreHex.vue'
  import SessionExpansion from './SessionExpansion.vue'

  // tabbable: this row is the grid's single Tab stop (its copy button too); others get tabindex -1.
  const {
    row,
    expanded,
    maxInterest,
    tabbable = true,
  } = defineProps<{
    row: SessionSummaryResponse
    expanded: boolean
    maxInterest: number
    tabbable?: boolean
  }>()
  const emit = defineEmits<{ toggle: [] }>()

  const story = computed(() => buildStory(row))
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
  const originFull = computed(() =>
    cityText.value ? `${countryText.value}, ${cityText.value}` : countryText.value,
  )
  const duration = computed(() => humanizeDuration(row.started_at, row.ended_at))
  // Normalized 0-100 against the dataset max; ScoreHex shows the same number.
  const displayScore = computed(() => Math.round(scoreFrac(row.interest, maxInterest) * 100))
  const started = computed(() => (row.started_at ? fmtRelativeTime(row.started_at) : '-'))

  // Prose accessibility: visible 12-char id is visual only, not read by screen readers.
  const ariaLabel = computed(
    () =>
      `Session from ${originFull.value}, interest score ${displayScore.value} of 100, lasting ${duration.value}`,
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

  function onKeydown(e: KeyboardEvent): void {
    if (e.target !== e.currentTarget) return
    const toggles =
      e.key === 'Enter' ||
      e.key === ' ' ||
      (e.key === 'ArrowRight' && !expanded) ||
      (e.key === 'ArrowLeft' && expanded)
    if (!toggles) return
    e.preventDefault()
    emit('toggle')
  }
</script>

<template>
  <!-- eslint-disable vuejs-accessibility/click-events-have-key-events -->
  <tr
    class="srow"
    :class="{ quiet: row.interest < 4 }"
    :data-id="row.id"
    :tabindex="tabbable ? 0 : -1"
    :aria-expanded="expanded"
    :aria-label="ariaLabel"
    @click="emit('toggle')"
    @keydown="onKeydown"
  >
    <td class="session">
      <div class="cell">
        <span class="chevron" :class="{ rotated: expanded }" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="14" height="14">
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </span>
        <ScoreHex :interest="row.interest" :ceiling="maxInterest" interactive />
        <span class="sid-wrap">
          <span class="sid">{{ row.id.slice(0, 12) }}</span>
          <button
            v-if="canCopy"
            type="button"
            class="sid-copy"
            :class="{ done: copied }"
            :tabindex="tabbable ? 0 : -1"
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
      </div>
    </td>
    <td class="story">
      <span class="badges">
        <HwBadge
          v-for="(b, i) in story"
          :key="i"
          :tone="b.tone"
          :title="b.title"
          :aria-label="b.title"
        >
          {{ b.label }}
          <svg v-if="b.icon" class="badge-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path :d="ICONS[b.icon]" />
          </svg>
        </HwBadge>
        <span class="dur" :title="`Lasted ${duration}`">{{ duration }}</span>
      </span>
    </td>
    <td class="origin">
      <div class="cell">
        <span class="flag" aria-hidden="true">{{ flag }}</span>
        <span class="country">{{ countryText }}</span>
        <template v-if="cityText">
          <span class="dot" aria-hidden="true">&middot;</span>
          <span class="city">{{ cityText }}</span>
        </template>
      </div>
    </td>
    <td class="spacer" aria-hidden="true"></td>
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
  }
  .cell {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
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

  /* Shrinks before the copy button does, so the button always stays inside the
     cell instead of spilling onto the story column. The id is decorative - the
     row's accessible name carries the real description. */
  .srow .sid {
    font-family: var(--font-mono);
    font-size: 12.5px;
    color: var(--accent);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .srow.quiet td {
    color: var(--text-dim);
  }

  .srow.quiet .sid {
    color: var(--accent-dim);
  }

  .sid-wrap {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 4px;
    min-width: 0;
  }

  /* Parked at the cell's trailing edge: sitting straight after the id put it
     under the middle of the row, where a tap meant to expand hit copy instead. */
  .sid-copy {
    margin-left: auto;
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
      opacity var(--motion-fast),
      color var(--motion-fast);
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
  @media (pointer: coarse) {
    .sid-copy {
      width: 32px;
      height: 32px;
      margin: -6px 0;
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

  .story {
    padding: 3px 10px !important;
  }

  .story .badges {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  /* Mobile only: the Duration column is hidden here, and duration is what tells look-alike rows apart. */
  .dur {
    display: none;
    font: 10.5px var(--font-mono);
    color: var(--text-dim);
  }

  /* The count carries the number; the glyph says what was counted, so the badge
     stays short enough to leave the id column its copy button. */
  .badge-icon {
    width: 11px;
    height: 11px;
    fill: currentColor;
    flex: none;
  }

  .origin {
    padding: 3px 10px !important;
    min-width: 0;
  }
  .origin .cell {
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
    /* Hide origin/spacer/duration/started; scoped to .srow so the colspan expansion cell stays visible. */
    .srow > td:nth-child(n + 3) {
      display: none;
    }

    .dur {
      display: inline;
    }
  }
</style>
