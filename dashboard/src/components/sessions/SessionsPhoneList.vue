<script setup lang="ts">
  // The sessions page on a phone: a list of two-line link rows. A look-alike run hangs under its
  // leader on a rail: a head button (count and chevron) opens the members. Presentational: the
  // view owns the data, the runs and the URL.
  import type { SessionRow } from '@/utils/sessionStory'
  import { fmtNumber } from '@/utils/format'
  import { ICONS } from '@/components/icons'
  import ChipButton from '@/components/base/ChipButton.vue'
  import SessionListRow from './SessionListRow.vue'

  const { rows, members, openRuns, sort, maxInterest, busy, runLoading, moreLabel } = defineProps<{
    rows: SessionRow[]
    members: Map<string, SessionRow[]>
    openRuns: Map<string, number>
    sort: string
    maxInterest: number
    busy: boolean
    runLoading: (first: string) => boolean
    moreLabel: (first: string) => string
  }>()
  const emit = defineEmits<{
    'toggle-run': [first: string]
    more: [first: string]
    open: [id: string]
  }>()

  const left = (row: SessionRow): number =>
    (row.run?.count ?? 0) - (members.get(row.id)?.length ?? 0)
  const kidsId = (first: string): string => `kids-${first}`
</script>

<template>
  <!-- eslint-disable vuejs-accessibility/no-redundant-roles -- Safari drops list semantics under list-style: none -->
  <ul class="sessions-phone" :class="{ busy }" :aria-busy="busy" aria-label="Sessions" role="list">
    <li v-for="row in rows" :key="row.id" :class="{ run: row.run, open: openRuns.has(row.id) }">
      <SessionListRow
        :row="row"
        :sort="sort"
        :max-interest="maxInterest"
        @open="emit('open', row.id)"
      />
      <template v-if="row.run">
        <button
          type="button"
          class="run-head"
          :aria-expanded="openRuns.has(row.id)"
          :aria-controls="kidsId(row.id)"
          @click="emit('toggle-run', row.id)"
        >
          <span class="cnt">{{ fmtNumber(row.run.count) }}</span>
          <span class="lbl">more like this</span>
          <svg class="cv" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path :d="ICONS['chevron-right']" />
          </svg>
        </button>
        <ul
          v-show="openRuns.has(row.id)"
          :id="kidsId(row.id)"
          class="kids"
          :aria-label="`Sessions like ${row.id.slice(0, 8)}`"
          role="list"
        >
          <li v-for="m in members.get(row.id) ?? []" :key="m.id">
            <SessionListRow
              :row="m"
              :sort="sort"
              :max-interest="maxInterest"
              child
              @open="emit('open', m.id)"
            />
          </li>
          <li v-if="runLoading(row.id) || left(row) > 0" class="more">
            <span v-if="runLoading(row.id)" role="status">Loading&hellip;</span>
            <ChipButton v-else @toggle="emit('more', row.id)">{{ moreLabel(row.id) }}</ChipButton>
          </li>
        </ul>
      </template>
    </li>
  </ul>
  <!-- eslint-enable vuejs-accessibility/no-redundant-roles -->
</template>

<style scoped>
  .sessions-phone {
    --lead-w: 26px;
    --row-h: 52px;
    --id-fs: 13px;
    --val-fs: 11.5px;
    --chip-sm: 11px;
    --head-h: 44px;
    --rail-x: 24px;
    --kid-indent: 56px;
    list-style: none;
    margin: 0;
    padding: 0;
    transition: opacity var(--motion-fast);
  }
  .sessions-phone.busy {
    opacity: 0.7;
  }
  .sessions-phone ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .sessions-phone > li {
    position: relative;
    border-top: 1px solid var(--border);
  }
  .sessions-phone > li:first-child {
    border-top: 0;
  }

  /* One rail under the leader's hex; the head and the children hang off it with ticks. */
  .run::before {
    content: '';
    position: absolute;
    left: var(--rail-x);
    top: 36px;
    bottom: calc(var(--head-h) / 2);
    width: 2px;
    border-radius: 1px;
    background: var(--border-strong);
  }
  .run.open::before {
    bottom: 26px;
    background: color-mix(in srgb, var(--accent) 55%, var(--border-strong));
  }
  .run-head {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-height: var(--head-h);
    padding: 0 12px 0 48px;
    box-sizing: border-box;
    border: 0;
    background: none;
    color: var(--text-muted);
    font: inherit;
    font-size: 12.5px;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .run-head::before {
    content: '';
    position: absolute;
    left: calc(var(--rail-x) + 1px);
    top: 50%;
    width: 15px;
    height: 1px;
    background: var(--border-strong);
  }
  .run-head:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .run-head[aria-expanded='true'] {
    color: var(--text);
  }
  .cnt {
    display: inline-grid;
    place-items: center;
    min-width: 26px;
    height: 22px;
    padding: 0 6px;
    box-sizing: border-box;
    border: 1px solid var(--border-strong);
    border-radius: 11px;
    background: var(--bg-0);
    font: 700 var(--val-fs) var(--font-mono);
    font-variant-numeric: tabular-nums;
    color: var(--text);
  }
  .lbl {
    flex: 1;
  }
  .cv {
    width: 16px;
    height: 16px;
    fill: currentColor;
    transition: transform var(--motion-fast);
  }
  .run-head[aria-expanded='true'] .cv {
    transform: rotate(90deg);
  }

  .run.open > .row {
    border-bottom: 1px solid var(--border-strong);
  }
  .run.open .run-head,
  .run.open .kids {
    background: color-mix(in srgb, var(--accent) 5%, transparent);
  }
  .more {
    display: flex;
    align-items: center;
    min-height: var(--head-h);
    padding-left: var(--kid-indent);
    border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
    color: var(--text-dim);
    font-size: var(--type-xs);
  }
  .more :deep(.chip) {
    min-height: var(--head-h);
  }
</style>
