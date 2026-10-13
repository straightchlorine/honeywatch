<script setup lang="ts">
  // One phone list row: a real link to the session. Two lines (id, then flag + place + the one
  // value the active sort orders by) and the story as bare icons. Children of an open run drop the
  // score hex, as the run's leader shows it once.
  import { computed } from 'vue'
  import type { SessionSummaryResponse } from '@/api/generated/types.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { fmtRelativeTime, fmtUtcStamp } from '@/utils/format'
  import { humanizeDuration } from '@/utils/duration'
  import { OUTCOME_TEXT, buildStory, outcomeBadge, scoreFrac } from '@/utils/sessionStory'
  import StoryChip from './StoryChip.vue'
  import ScoreHex from './ScoreHex.vue'

  const {
    row,
    sort = 'interest',
    maxInterest,
    child = false,
  } = defineProps<{
    row: SessionSummaryResponse
    sort?: string
    maxInterest: number
    child?: boolean
  }>()
  const emit = defineEmits<{ open: [] }>()

  const flag = computed(() => useCountryFlag(row.country_code))
  const countryText = computed(() => row.country ?? row.country_code ?? 'Unknown')
  // A city that repeats the country (Singapore) is dropped.
  const cityText = computed(() => {
    const city = row.city?.trim()
    return city && city.toLowerCase() !== countryText.value.trim().toLowerCase() ? city : null
  })
  const place = computed(() =>
    sort === 'country' ? countryText.value : (cityText.value ?? countryText.value),
  )
  const value = computed<string | null>(() => {
    if (sort === 'recent') return row.started_at ? fmtRelativeTime(row.started_at) : '-'
    if (sort === 'duration') return humanizeDuration(row.started_at, row.ended_at)
    return null
  })
  // Counts when there are any; otherwise the outcome stands alone as a bare icon.
  const chips = computed(() => {
    const counts = buildStory(row).filter((b) => b.icon)
    return counts.length ? counts : [outcomeBadge(row.category)]
  })
  const score = computed(() => Math.round(scoreFrac(row.interest, maxInterest) * 100))
  const id = computed(() => row.id.slice(0, 8))
  const label = computed(
    () =>
      `${id.value}, ${cityText.value ? `${cityText.value}, ` : ''}${countryText.value}, ${OUTCOME_TEXT[row.category].toLowerCase()}, interest ${score.value} of 100`,
  )
</script>

<template>
  <RouterLink
    class="row"
    :class="{ child, quiet: row.interest < 4 }"
    :to="{ name: 'session-detail', params: { id: row.id } }"
    :data-id="row.id"
    :aria-label="label"
    :title="fmtUtcStamp(row.started_at)"
    @click="emit('open')"
  >
    <span v-if="!child" class="lead" aria-hidden="true">
      <ScoreHex :interest="row.interest" :ceiling="maxInterest" />
    </span>
    <span class="l1 id">{{ id }}</span>
    <span class="l2">
      <span class="flag" role="img" :aria-label="countryText" :title="countryText">{{ flag }}</span>
      <span class="place">{{ place }}</span>
      <span v-if="value" class="val">{{ value }}</span>
    </span>
    <span class="chips">
      <StoryChip
        v-for="(b, i) in chips"
        :key="i"
        role="img"
        :tone="b.tone"
        :icon="b.icon"
        :glyph="b.glyph"
        icon-only
        :title="b.title"
        :aria-label="b.title"
      >
        {{ b.label }}
      </StoryChip>
    </span>
  </RouterLink>
</template>

<style scoped>
  .row {
    position: relative;
    display: grid;
    grid-template-columns: var(--lead-w) minmax(0, 1fr) auto;
    column-gap: 10px;
    align-items: center;
    min-height: var(--row-h);
    padding: 6px 12px;
    box-sizing: border-box;
    color: inherit;
    text-decoration: none;
    -webkit-tap-highlight-color: transparent;
  }
  .row:active {
    background: var(--surface-hover);
  }
  .row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .lead {
    grid-row: 1 / 3;
    display: flex;
    justify-content: center;
  }
  .lead :deep(.score-hex) {
    width: var(--lead-w);
    height: 28px;
  }
  .l1,
  .l2 {
    grid-column: 2;
    min-width: 0;
    display: flex;
    align-items: center;
  }
  .id {
    height: 18px;
    font: 600 var(--id-fs) / 18px var(--font-mono);
    letter-spacing: 0.01em;
    color: var(--accent);
  }
  .row:visited .id {
    color: var(--text-muted);
  }
  /* --accent-dim is 3.2:1 on the card; this stays recessive and passes 4.5:1. */
  .row.quiet .id {
    color: color-mix(in srgb, var(--accent) 82%, var(--bg-0));
  }
  .l2 {
    gap: 6px;
    height: 16px;
    margin-top: 2px;
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
  }
  .row.quiet .l2 {
    color: var(--text-dim);
  }
  .flag {
    flex: none;
    font-size: 14px;
    line-height: 1;
  }
  .place {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .val {
    flex: none;
    font: 500 var(--val-fs) var(--font-mono);
    font-variant-numeric: tabular-nums;
    color: var(--text-dim);
  }
  .chips {
    grid-column: 3;
    grid-row: 1 / 3;
    display: flex;
    gap: 5px;
    align-items: center;
    justify-content: flex-end;
  }
  .chips :deep(.chip) {
    --cut: 5px;
    height: 20px;
    padding: 0 calc(var(--cut) + 3px);
    gap: 4px;
    font-size: var(--chip-sm);
  }
  .chips :deep(.chip-icon:not(.glyph)) {
    width: 12px;
    height: 12px;
  }

  .row.child {
    grid-template-columns: minmax(0, 1fr) auto;
    padding-left: var(--kid-indent);
    border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
  }
  .child .l1,
  .child .l2 {
    grid-column: 1;
  }
  .child .chips {
    grid-column: 2;
  }
  .row.child::before {
    content: '';
    position: absolute;
    left: calc(var(--rail-x) + 1px);
    top: 50%;
    width: 20px;
    height: 1px;
    background: var(--border-strong);
  }
</style>
