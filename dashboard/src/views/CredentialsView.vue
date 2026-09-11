<script setup lang="ts">
  /**
   * Credentials page: combination comb (HexMatrix) of top usernames x top
   * passwords with acceptance status, plus password-anatomy histogram.
   */
  import { computed, ref } from 'vue'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import {
    statsAuthOutcomesOptions,
    statsPasswordCompositionOptions,
    statsPasswordsByLengthOptions,
    statsTopCredentialsOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import ChipButton from '@/components/base/ChipButton.vue'
  import InfoDot from '@/components/base/InfoDot.vue'
  import SeqLegend from '@/components/base/SeqLegend.vue'
  import InsightNote from '@/components/base/InsightNote.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import RankList, { type RankRow } from '@/components/base/RankList.vue'
  import DrawerShell from '@/components/base/DrawerShell.vue'
  import HexMatrix, { type MatrixCellSelection } from '@/components/charts/HexMatrix.vue'
  import MeterBar from '@/components/charts/MeterBar.vue'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { fmtCompact, fmtNumber } from '@/utils/format'
  import {
    buildCharsetRows,
    buildLengthBars,
    buildMatrixEntities,
    buildMatrixPairs,
    buildPairBarRows,
    buildPasswordRows,
    fmtSuccessRate,
    type BarRow,
  } from '@/utils/credentials'

  // These endpoints send Cache-Control: max-age=120, so polling faster than that
  // only re-reads the browser's own cache and never reaches the API. One value,
  // matching the cache, instead of two that pretend to be quicker.
  const POLL_MS = 120_000
  const MATRIX_USERS = 8
  // API max is 100 (validate.Range in common.py); HexMatrix reports actual
  // drawn count via @shown, so fetch conservatively.
  const MATRIX_PASSWORDS_TOP_N = 100

  const usersQ = useQuery({
    ...statsTopCredentialsOptions({ query: { by: 'username', top_n: MATRIX_USERS } }),
    refetchInterval: POLL_MS,
  })
  const passwordsQ = useQuery({
    ...statsTopCredentialsOptions({ query: { by: 'password', top_n: MATRIX_PASSWORDS_TOP_N } }),
    refetchInterval: POLL_MS,
  })
  // Top pairs overall (any outcome); matrix cells use real counts, not estimates.
  const pairsQ = useQuery({
    ...statsTopCredentialsOptions({ query: { by: 'pair', top_n: 100 } }),
    refetchInterval: POLL_MS,
  })
  const workedQ = useQuery({
    ...statsTopCredentialsOptions({ query: { by: 'pair', outcome: 'success', top_n: 10 } }),
    refetchInterval: POLL_MS,
  })
  const outcomesQ = useQuery({
    ...statsAuthOutcomesOptions(),
    refetchInterval: POLL_MS,
    staleTime: POLL_MS,
  })
  const compositionQ = useQuery({
    ...statsPasswordCompositionOptions(),
    refetchInterval: POLL_MS,
    staleTime: POLL_MS,
  })

  await Promise.all([
    usersQ.suspense(),
    passwordsQ.suspense(),
    pairsQ.suspense(),
    workedQ.suspense(),
    outcomesQ.suspense(),
    compositionQ.suspense(),
  ])

  const outcomes = computed(() => outcomesQ.data.value!)
  const composition = computed(() => compositionQ.data.value!)

  const matrixUsers = computed(() => buildMatrixEntities(usersQ.data.value ?? [], 'username'))
  const matrixPasswords = computed(() =>
    buildMatrixEntities(passwordsQ.data.value ?? [], 'password'),
  )
  const matrixPairs = computed(() =>
    buildMatrixPairs(pairsQ.data.value ?? [], workedQ.data.value ?? []),
  )
  // Legend hot end uses top pair count (already sorted) as proxy for matrix max.
  const legendMax = computed(() => pairsQ.data.value?.[0]?.count ?? 0)

  // Init to fetch size for sane meta text before ResizeObserver first callback.
  const shownPasswordCount = ref(matrixPasswords.value.length)

  const workedRows = computed<RankRow[]>(() =>
    toRankRows(buildPairBarRows(workedQ.data.value ?? [])),
  )

  // Drill-down built from page data only (no by-pair endpoint); uses marginals
  // for context.
  const selectedCell = ref<MatrixCellSelection | null>(null)
  const selectedCellKey = computed(() =>
    selectedCell.value ? `${selectedCell.value.username}|${selectedCell.value.password}` : null,
  )
  const cellTitle = computed(() =>
    selectedCell.value ? `${selectedCell.value.username}:${selectedCell.value.password}` : '',
  )

  function selectCell(cell: MatrixCellSelection): void {
    selectedCell.value = cell
  }
  function closeCellDrawer(): void {
    selectedCell.value = null
  }

  // Rank within the observed universe only (pairsQ top 100 + accepted-only);
  // avoid false precision.
  const observedPairsByCount = computed(() =>
    [...matrixPairs.value].sort((a, b) => b.count - a.count),
  )
  const cellRank = computed(() => {
    if (!selectedCell.value?.observed) return null
    const idx = observedPairsByCount.value.findIndex(
      (p) =>
        p.username === selectedCell.value!.username && p.password === selectedCell.value!.password,
    )
    return idx === -1 ? null : idx + 1
  })
  const cellSharePct = computed(() => {
    if (!selectedCell.value || outcomes.value.total <= 0) return null
    return (selectedCell.value.count / outcomes.value.total) * 100
  })
  // Row/column marginals come from the username/password endpoints, which
  // aggregate across *every* counterpart - not just the ones that made the
  // matrix - so these totals hold even when the matrix can't show the pair.
  const cellRowTotal = computed(
    () => matrixUsers.value.find((u) => u.label === selectedCell.value?.username)?.count ?? 0,
  )
  const cellColTotal = computed(
    () => matrixPasswords.value.find((p) => p.label === selectedCell.value?.password)?.count ?? 0,
  )
  const cellRowFrac = computed(() =>
    selectedCell.value && cellRowTotal.value > 0
      ? selectedCell.value.count / cellRowTotal.value
      : 0,
  )
  const cellColFrac = computed(() =>
    selectedCell.value && cellColTotal.value > 0
      ? selectedCell.value.count / cellColTotal.value
      : 0,
  )

  const topUser = computed(() => matrixUsers.value[0] ?? null)
  const topUserSharePct = computed(() => {
    if (!topUser.value || outcomes.value.total <= 0) return null
    return (topUser.value.count / outcomes.value.total) * 100
  })

  const acceptFrac = computed(() =>
    outcomes.value.total > 0 ? outcomes.value.successful / outcomes.value.total : 0,
  )

  // Password anatomy: KPIs and charts must use same query for consistency.
  const lengthBars = computed(() =>
    buildLengthBars(composition.value.lengths, composition.value.capped_at),
  )
  const modeBar = computed(() => {
    let best: (typeof lengthBars.value)[number] | null = null
    for (const b of lengthBars.value) {
      if (!best || b.count > best.count) best = b
    }
    return best
  })
  const charsetRows = computed<RankRow[]>(() =>
    toRankRows(buildCharsetRows(composition.value.classes)),
  )

  type AnatomyTab = 'length' | 'composition'
  const anatomyTab = ref<AnatomyTab>('length')

  const selectedLength = ref<number | null>(null)
  const passwordsByLengthQ = useQuery(
    computed(() => ({
      ...statsPasswordsByLengthOptions({ query: { length: selectedLength.value ?? 0, top_n: 25 } }),
      enabled: selectedLength.value !== null,
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  const drillRows = computed<RankRow[]>(() =>
    toRankRows(buildPasswordRows(passwordsByLengthQ.data.value ?? [])),
  )
  const selectedLabel = computed(() => {
    if (selectedLength.value === null) return ''
    return selectedLength.value >= composition.value.capped_at
      ? `${composition.value.capped_at}+`
      : String(selectedLength.value)
  })

  // Transition out-in unmounts the old control before mounting the new one,
  // dropping focus to body. Restore focus to a sensible control (WCAG 2.4.3)
  // in after-enter, not nextTick: out-in only mounts the entering view once the
  // leave transition has finished, so at nextTick there is nothing to focus yet.
  const backBtnRef = ref<HTMLButtonElement | null>(null)
  const histBarsRef = ref<HTMLElement | null>(null)
  type FocusTarget = 'back' | 'hist' | null
  const pendingFocus = ref<FocusTarget>(null)

  function onAnatomyEntered(): void {
    const target = pendingFocus.value
    pendingFocus.value = null
    if (target === 'back') backBtnRef.value?.focus()
    else if (target === 'hist') histBarsRef.value?.focus()
  }

  const tooltip = useHwTooltip()

  // Hide the tooltip on any view swap: the hovered trigger (a histogram bar)
  // unmounts during the transition without firing a leave event, so the
  // bubble would otherwise stay frozen on screen.
  function selectLength(length: number): void {
    tooltip.hide(true)
    pendingFocus.value = 'back'
    selectedLength.value = length
  }
  function clearLength(): void {
    tooltip.hide(true)
    pendingFocus.value = 'hist'
    selectedLength.value = null
  }

  // Switching tabs always lands back on the histogram - resuming a drilled-in
  // state after a detour through Composition would be a surprise, not a feature.
  function setAnatomyTab(tab: AnatomyTab): void {
    if (tab === anatomyTab.value) return
    tooltip.hide(true)
    anatomyTab.value = tab
    selectedLength.value = null
  }

  /** RankRow adapter for the count/bar rows credentials.ts already builds. */
  function toRankRows(rows: BarRow[]): RankRow[] {
    let max = 0
    for (const r of rows) if (r.count > max) max = r.count
    return rows.map((r) => ({
      label: r.label,
      value: fmtNumber(r.count),
      frac: max > 0 ? r.count / max : 0,
      title: r.title,
    }))
  }

  const TOOLTIP_COMB =
    'Rows are the top usernames, columns the top passwords. Darker means more attempts - a ring means the honeypot let that pair in.'
  const TOOLTIP_WORKED =
    'The honeypot lets some logins through on purpose, to watch what an attacker does next. It is not a real weak password.'
  const TOOLTIP_ANATOMY =
    'The length and character types of every password attackers have tried here.'
  const TOOLTIP_LENGTH = 'How many passwords have each length. Click a bar to see them.'
  const TOOLTIP_COMPOSITION =
    'What passwords are made of - digits only, letters only, mixed, or with symbols.'
  const TOOLTIP_DISTINCT_PASSWORDS = 'Every different password ever tried against the honeypot.'
  const TOOLTIP_DISTINCT_USERNAMES =
    'Every different username ever tried, whatever password went with it.'
  const TOOLTIP_AUTH_ATTEMPTS =
    'Every login attempt this honeypot has logged, successful or not, since it started collecting.'
  const TOOLTIP_ACCEPTED =
    'Share of attempts the honeypot let through on purpose, to watch what an attacker does next. Not a real weakness.'
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="credentials" />
    </template>

    <div class="cred-page">
      <div class="page-head">
        <h1>Credentials</h1>
        <span class="sub"
          >{{ fmtNumber(outcomes.total) }} guesses at the door &middot; what got them in</span
        >
      </div>

      <div class="stat-row">
        <StatTile label="Distinct passwords" :value="fmtNumber(outcomes.unique_passwords)">
          <template #label-extra>
            <InfoDot title="Distinct passwords" :text="TOOLTIP_DISTINCT_PASSWORDS" />
          </template>
          <template #meta>top {{ shownPasswordCount }} shown in the grid below</template>
        </StatTile>
        <StatTile label="Distinct usernames" :value="fmtNumber(outcomes.unique_usernames)">
          <template #label-extra>
            <InfoDot title="Distinct usernames" :text="TOOLTIP_DISTINCT_USERNAMES" />
          </template>
          <template #meta>
            <template v-if="topUser">
              {{ topUser.label }} alone: {{ fmtNumber(topUser.count) }} attempts
            </template>
          </template>
        </StatTile>
        <StatTile label="Login attempts" :value="fmtNumber(outcomes.total)">
          <template #label-extra>
            <InfoDot title="Login attempts" :text="TOOLTIP_AUTH_ATTEMPTS" />
          </template>
          <template #meta>all time</template>
        </StatTile>
        <StatTile label="Accepted" :value="fmtSuccessRate(outcomes.success_rate)">
          <template #label-extra>
            <InfoDot title="Accepted" :text="TOOLTIP_ACCEPTED" />
          </template>
          <template #meta>{{ fmtNumber(outcomes.successful) }} accepted attempts</template>
        </StatTile>
      </div>

      <div class="grid-main">
        <HwCard class="matrix-card" title="Username and password pairs">
          <template #head-extra>
            <InfoDot title="Username and password pairs" :text="TOOLTIP_COMB" />
            <div class="matrix-legend">
              <SeqLegend min="rare" :max="`${fmtCompact(legendMax)} attempts`" />
              <span class="accept-legend"><span class="ring" aria-hidden="true" />accepted</span>
            </div>
          </template>
          <HexMatrix
            :users="matrixUsers"
            :passwords="matrixPasswords"
            :pairs="matrixPairs"
            :selected-key="selectedCellKey"
            @select="selectCell"
            @shown="shownPasswordCount = $event"
          />
          <InsightNote v-if="topUser && topUserSharePct !== null" class="matrix-insight">
            The username <b>{{ topUser.label }}</b> alone drives {{ topUserSharePct.toFixed(1) }}%
            of all attempts ({{ fmtNumber(topUser.count) }}
            attempts).
          </InsightNote>
        </HwCard>

        <div class="right-col">
          <HwCard class="worked-card" title="What worked">
            <template #head-extra>
              <InfoDot title="What worked" :text="TOOLTIP_WORKED" />
            </template>
            <MeterBar :frac="acceptFrac" fill="var(--ok)" />
            <div class="cap">
              <span
                ><b>{{ fmtNumber(outcomes.successful) }} accepted</b> &middot;
                {{ fmtSuccessRate(outcomes.success_rate) }}</span
              >
              <span>{{ fmtNumber(outcomes.failed) }} rejected</span>
            </div>
            <RankList
              v-if="workedRows.length"
              class="worked-list"
              :rows="workedRows"
              label-width="138px"
              mono
              fill="var(--ok)"
            />
            <EmptyState v-else class="worked-list" title="Nothing accepted yet" />
          </HwCard>

          <HwCard title="Password anatomy" class="anatomy-card">
            <template #head-extra>
              <InfoDot title="Password anatomy" :text="TOOLTIP_ANATOMY" />
              <span class="toggle-row">
                <ChipButton :pressed="anatomyTab === 'length'" @toggle="setAnatomyTab('length')">
                  Length
                  <template #trailing>
                    <InfoDot title="Length" :text="TOOLTIP_LENGTH" />
                  </template>
                </ChipButton>
                <ChipButton
                  :pressed="anatomyTab === 'composition'"
                  @toggle="setAnatomyTab('composition')"
                >
                  Composition
                  <template #trailing>
                    <InfoDot title="Composition" :text="TOOLTIP_COMPOSITION" />
                  </template>
                </ChipButton>
              </span>
            </template>

            <template v-if="anatomyTab === 'length'">
              <Transition name="anatomy-fade" mode="out-in" @after-enter="onAnatomyEntered">
                <div v-if="selectedLength === null" key="hist" class="anatomy-body">
                  <div
                    class="hist"
                    role="group"
                    aria-label="Password lengths. Click a bar to see its passwords."
                  >
                    <div ref="histBarsRef" class="hist-bars" tabindex="-1">
                      <button
                        v-for="bar in lengthBars"
                        :key="bar.key"
                        type="button"
                        class="hist-col"
                        :class="{ peak: modeBar && bar.key === modeBar.key }"
                        :disabled="bar.count === 0"
                        :aria-label="`Show the ${bar.count} passwords of ${bar.label || bar.length} characters`"
                        @click="selectLength(bar.length)"
                        @mouseenter="tooltip.show(bar.title)"
                        @mousemove="tooltip.move($event)"
                        @mouseleave="tooltip.hide()"
                        @focus="tooltip.show(bar.title)"
                        @blur="tooltip.hide()"
                      >
                        <span class="hist-bar" :style="{ height: bar.heightPct }" />
                      </button>
                    </div>
                    <div class="hist-axis" aria-hidden="true">
                      <span v-for="bar in lengthBars" :key="`x-${bar.key}`" class="hist-tick">
                        {{ bar.label }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Drill-down: fixed-height list of passwords at chosen length; no reflow on swap. -->
                <div v-else key="drill" class="drill">
                  <div class="drill-head">
                    <button ref="backBtnRef" type="button" class="back-btn" @click="clearLength">
                      <span aria-hidden="true">&#8592;</span> Anatomy
                    </button>
                    <span class="drill-title">{{ selectedLabel }} characters</span>
                  </div>
                  <div class="drill-scroll">
                    <p v-if="passwordsByLengthQ.isError.value" class="drill-error" role="status">
                      Couldn't load passwords for this length - retrying.
                    </p>
                    <RankList v-else :rows="drillRows" label-width="200px" mono />
                  </div>
                </div>
              </Transition>
            </template>
            <template v-else>
              <div class="anatomy-body">
                <RankList class="comp-list" :rows="charsetRows" label-width="122px" />
              </div>
            </template>
          </HwCard>
        </div>
      </div>

      <DrawerShell :open="!!selectedCell" :title="cellTitle" @close="closeCellDrawer">
        <template v-if="selectedCell" #head-extra>
          <span v-if="selectedCell.accepted" class="pd-badge ok">accepted</span>
          <span v-else-if="!selectedCell.observed" class="pd-badge dim">never tried</span>
        </template>
        <template v-if="selectedCell">
          <div class="pd-hero">
            <span class="n">{{ fmtNumber(selectedCell.count) }}</span>
            <span class="l">attempts<br />at this exact pair</span>
          </div>

          <InsightNote v-if="selectedCell.observed">
            Ranks <b>#{{ cellRank ?? '?' }}</b> of
            {{ fmtNumber(observedPairsByCount.length) }} pairs tried &middot;
            <b>{{ cellSharePct !== null ? cellSharePct.toFixed(2) : '-' }}%</b> of all attempts.
            <span v-if="selectedCell.accepted">The honeypot accepted this exact combination.</span>
          </InsightNote>
          <InsightNote v-else>
            This exact pair has never been tried against the honeypot.
          </InsightNote>

          <div class="pd-grid">
            <div>
              <span class="k">{{ selectedCell.username }}, all passwords</span>
              <span class="v">{{ fmtNumber(cellRowTotal) }}</span>
            </div>
            <div>
              <span class="k">{{ selectedCell.password }}, all usernames</span>
              <span class="v">{{ fmtNumber(cellColTotal) }}</span>
            </div>
          </div>

          <div class="pd-share">
            <span class="pd-share-label">Share of {{ selectedCell.username }}'s attempts</span>
            <MeterBar :frac="cellRowFrac" />
          </div>
          <div class="pd-share">
            <span class="pd-share-label">Share of {{ selectedCell.password }}'s attempts</span>
            <MeterBar :frac="cellColFrac" />
          </div>
        </template>
      </DrawerShell>
    </div>
  </PageShell>
</template>

<style scoped>
  .cred-page {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .page-head {
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex: none;
    flex-wrap: wrap;
  }

  .page-head h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.005em;
    color: var(--text);
  }

  .sub {
    color: var(--text-dim);
    font-size: 13px;
  }

  .matrix-legend {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-left: auto;
  }

  .accept-legend {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font: 500 11px var(--font-mono);
    color: var(--text-dim);
  }

  .accept-legend .ring {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    border: 1.5px solid var(--ok);
    display: inline-block;
  }

  .stat-row {
    flex: none;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    gap: 12px;
  }

  /* Full-width comb clips "What worked" and "Password anatomy" cards. Grid
     with near-square comb (1.2fr/1fr) gives both columns proper space. */
  .grid-main {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    gap: 14px;
  }

  .matrix-card :deep(svg.hex-matrix) {
    flex: 1;
    min-height: 0;
  }

  .matrix-insight {
    margin-top: 8px;
  }

  .right-col {
    display: grid;
    grid-template-rows: 1fr 1fr;
    gap: 14px;
    min-height: 0;
  }

  .worked-card {
    min-height: 0;
  }

  .cap {
    display: flex;
    justify-content: space-between;
    font: 500 11.5px var(--font-mono);
    color: var(--text-dim);
    margin: 6px 0 8px;
  }

  .cap b {
    color: var(--ok);
    font-weight: 600;
  }

  /* min-height:0 lets RankList scroll inside the card instead of overflowing it. */
  .worked-list {
    flex: 1 1 auto;
    min-height: 0;
  }

  .anatomy-card {
    min-height: 0;
  }

  /* h2's uppercase/letter-spacing are inherited - reset so labels render as typed. */
  .toggle-row {
    display: flex;
    gap: 6px;
    margin-left: auto;
    text-transform: none;
    letter-spacing: normal;
    flex-wrap: wrap;
    align-items: center;
  }

  .anatomy-body,
  .drill {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* flex:1 works because .right-col height chain to PageShell is definite,
     giving bars' percentage heights a base to resolve against. */
  .hist {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hist-bars {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    align-items: flex-end;
    gap: 2px;
  }

  .hist-bars:focus {
    outline: none;
  }
  .hist-bars:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 2px;
    border-radius: 4px;
  }

  .hist-col {
    flex: 1 1 0;
    height: 100%;
    display: flex;
    align-items: flex-end;
    border: 0;
    padding: 0;
    background: transparent;
    cursor: pointer;
  }

  .hist-col:disabled {
    cursor: default;
  }

  .hist-col:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 2px;
    border-radius: 4px;
  }

  .hist-bar {
    width: 100%;
    background: var(--series-1);
    border-radius: 2.5px 2.5px 0 0;
    transition: background var(--motion-fast);
  }

  .hist-col.peak .hist-bar {
    background: var(--accent);
  }

  .hist-col:hover:not(:disabled) .hist-bar {
    filter: brightness(1.2);
  }

  .hist-axis {
    display: flex;
    gap: 2px;
  }

  .hist-tick {
    flex: 1 1 0;
    text-align: center;
    font: 500 9.5px var(--font-mono);
    color: var(--text-dim);
    overflow: visible;
    white-space: nowrap;
  }

  .hist-tick:first-child {
    text-align: left;
  }
  .hist-tick:last-child {
    text-align: right;
  }

  .comp-list {
    flex: 1 1 auto;
    min-height: 0;
  }

  .drill-head {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .back-btn {
    border: 1px solid var(--border-strong);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 12px;
    padding: 5px 10px;
    border-radius: var(--radius-md);
    transition:
      color var(--motion-fast),
      border-color var(--motion-fast);
  }

  .back-btn:hover {
    color: var(--text);
    border-color: var(--accent-dim);
  }

  .back-btn:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 2px;
  }

  .drill-title {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }

  .drill-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .drill-error {
    margin: 0;
    font-size: 12px;
    color: var(--warning);
  }

  .anatomy-fade-enter-active,
  .anatomy-fade-leave-active {
    transition: opacity var(--motion-fast) ease;
    pointer-events: none;
  }
  .anatomy-fade-enter-from,
  .anatomy-fade-leave-to {
    opacity: 0;
  }

  /* Comb-cell drawer content (DrawerShell owns the chrome). */
  .pd-hero {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .pd-hero .n {
    font-family: var(--font-mono);
    font-size: 36px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  .pd-hero .l {
    color: var(--text-dim);
    font-size: 12px;
  }

  .pd-badge {
    font: 600 10px var(--font-mono);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 999px;
    border: 1px solid transparent;
  }

  .pd-badge.ok {
    color: var(--ok);
    background: rgba(132, 204, 22, 0.1);
    border-color: rgba(132, 204, 22, 0.28);
  }

  .pd-badge.dim {
    color: var(--text-dim);
    background: var(--surface-2);
    border-color: var(--border);
  }

  .pd-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .pd-grid > div {
    min-width: 0;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .pd-grid .k {
    font: 600 10px var(--font-sans);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pd-grid .v {
    font: 620 16px var(--font-sans);
    color: var(--text);
  }

  .pd-share {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .pd-share-label {
    font-size: 11.5px;
    color: var(--text-muted);
  }

  @media (max-width: 900px) {
    .cred-page {
      overflow-y: auto;
    }

    .stat-row {
      grid-auto-flow: row;
      grid-template-columns: 1fr 1fr;
    }

    .grid-main {
      display: flex;
      flex-direction: column;
    }

    /* Own row under the title, with the ramp and the accepted key pushed apart
       so they stop reading as one run-on label. */
    .matrix-legend {
      flex-wrap: wrap;
      margin-left: 0;
      flex-basis: 100%;
      justify-content: space-between;
      gap: 6px 14px;
    }

    .matrix-card :deep(svg.hex-matrix) {
      min-height: 260px;
    }

    .right-col {
      display: flex;
      flex-direction: column;
    }

    .anatomy-card,
    .worked-card {
      flex: none;
      height: auto;
    }

    /* Card is height:auto on mobile; fall back to fixed height so bars'
       percentage heights don't collapse. */
    .hist {
      flex: none;
      height: 180px;
    }

    /* The card is height:auto on mobile, so flex:1 on the list has nothing
       to grow into; cap it so it scrolls internally instead of stretching
       the whole (already-scrolling) page. */
    .worked-list {
      max-height: 168px;
    }

    /* The card title takes the first line, so the chips get a full row and stay
       side by side instead of stacking. */
    .toggle-row {
      margin-left: 0;
      flex-basis: 100%;
      flex-wrap: nowrap;
    }
  }
</style>
