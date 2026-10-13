<script setup lang="ts">
  // One row standing in for a run of look-alike sessions under its first session. The row is the
  // grid's roving stop. The other columns summarise the folded sessions (the API's run summary) so
  // it reads as part of the grid.
  import { computed } from 'vue'
  import type { RunSummaryResponse } from '@/api/generated/types.gen'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { fmtNumber, fmtRelativeTime } from '@/utils/format'
  import { buildStory, type SessionRow } from '@/utils/sessionStory'
  import { ICONS } from '@/components/icons'
  import StoryChip from './StoryChip.vue'

  const {
    row,
    run,
    open,
    tabbable = false,
  } = defineProps<{ row: SessionRow; run: RunSummaryResponse; open: boolean; tabbable?: boolean }>()
  const emit = defineEmits<{ toggle: [] }>()

  // The run shares its first session's story, so these chips stand for every row beneath.
  const story = computed(() => buildStory(row))
  // minutes above 60s
  const sec = (s: number): string => (s < 60 ? `${s}s` : `${Math.round(s / 60)}m`)
  const duration = computed(() => {
    const { min_duration_s: lo, max_duration_s: hi } = run
    if (lo === null || hi === null) return '-'
    if (lo === hi) return sec(lo)
    if (hi < 60) return `${lo}-${hi}s`
    const [a, b] = [sec(lo), sec(hi)]
    return a === b ? a : `${a}-${b}`
  })
  const started = computed(() => {
    const [a, b] = [fmtRelativeTime(run.newest), fmtRelativeTime(run.oldest)]
    return a === b ? a : `${a} to ${b}`
  })
  // "105d ago to 106d ago" -> "105-106d ago" for the tablet band, where the column is too narrow.
  const startedShort = computed(() => {
    const [a, b] = [fmtRelativeTime(run.newest), fmtRelativeTime(run.oldest)]
    if (a === b) return a
    const [ma, mb] = [/^(\d+)(\D+?) ago$/.exec(a), /^(\d+)(\D+?) ago$/.exec(b)]
    if (!ma || !mb) return a
    return ma[2] === mb[2]
      ? `${ma[1]}-${mb[1]}${ma[2]} ago`
      : `${ma[1]}${ma[2]}-${mb[1]}${mb[2]} ago`
  })
  const origin = computed(() => {
    const name = run.country ?? run.country_code
    if (run.countries === 1 && name) return `${useCountryFlag(run.country_code)} ${name}`
    return run.countries ? `${run.countries} countries` : '-'
  })

  function onKeydown(e: KeyboardEvent): void {
    if (e.target !== e.currentTarget) return
    if (
      ['Enter', ' '].includes(e.key) ||
      (e.key === 'ArrowRight' && !open) ||
      (e.key === 'ArrowLeft' && open)
    ) {
      e.preventDefault()
      emit('toggle')
    }
  }
</script>

<template>
  <!-- eslint-disable vuejs-accessibility/click-events-have-key-events -->
  <tr
    class="sgroup"
    :tabindex="tabbable ? 0 : -1"
    :aria-expanded="open"
    @click="emit('toggle')"
    @keydown="onKeydown"
  >
    <td class="g">
      <span class="label">
        <span class="chevron" :class="{ rotated: open }" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="14" height="14">
            <path :d="ICONS['chevron-right']" fill="currentColor" />
          </svg>
        </span>
        <span v-if="open" class="hide">Hide</span>
        <StoryChip>{{ fmtNumber(run.count) }}</StoryChip>
        more like this
      </span>
    </td>
    <td class="g">
      <span class="chips">
        <StoryChip
          v-for="(b, i) in story"
          :key="i"
          :tone="b.tone"
          :icon="b.icon"
          :glyph="b.glyph"
          :title="b.title"
          :aria-label="b.title"
        >
          {{ b.label }}
        </StoryChip>
      </span>
    </td>
    <td class="g">{{ origin }}</td>
    <td class="g" aria-hidden="true"></td>
    <td class="g r num">{{ duration }}</td>
    <td class="g r started" :title="started">
      <span class="full">{{ started }}</span
      ><span class="short">{{ startedShort }}</span>
    </td>
  </tr>
  <!-- eslint-enable vuejs-accessibility/click-events-have-key-events -->
</template>

<style scoped>
  .sgroup {
    transition: background var(--motion-fast);
  }
  .sgroup:hover {
    background: var(--surface-hover);
  }
  /* td.g outranks the parent table's td padding (a plain scoped class would lose to it). The
     28px start lines the chevron up with the score hex of the session rows above. */
  .sgroup td.g {
    padding-block: 4px;
    color: var(--text-dim);
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sgroup td.g:first-child {
    padding-left: 28px;
  }
  .sgroup td.started {
    padding-right: 14px;
    font-size: 11.5px;
  }
  .short {
    display: none;
  }
  @media (min-width: 760px) and (max-width: 1179.98px) {
    .full {
      display: none;
    }
    .short {
      display: inline;
    }
    .hide {
      display: none;
    }
  }
  .chips {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .sgroup td.g:nth-child(n + 3) {
    font-style: italic;
    opacity: 0.85;
  }
  .label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-weight: 550;
  }
  .sgroup:hover .label,
  .sgroup:focus-visible .label {
    color: var(--accent);
  }
  .chevron {
    display: inline-flex;
    flex: 0 0 auto;
    transition: transform var(--motion-fast);
  }
  .chevron.rotated {
    transform: rotate(90deg);
  }
  @media (pointer: coarse) and (min-width: 760px) {
    .sgroup td.g {
      padding-block: 12px;
    }
  }
</style>
