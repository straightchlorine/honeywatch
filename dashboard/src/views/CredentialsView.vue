<script setup lang="ts">
  import { computed, ref } from 'vue'
  import { useQuery, keepPreviousData } from '@tanstack/vue-query'
  import {
    statsAuthOutcomesOptions,
    statsPasswordCompositionOptions,
    statsPasswordsByLengthOptions,
    statsTopCredentialsOptions,
  } from '@/api/queries'
  import Card from '@/components/base/Card.vue'
  import Stat from '@/components/base/Stat.vue'
  import BarList from '@/components/base/BarList.vue'
  import PageHeader from '@/components/base/PageHeader.vue'
  import EmptyState from '@/components/base/EmptyState.vue'
  import Tooltip from '@/components/base/Tooltip.vue'
  import { useTooltip } from '@/components/base/useTooltip'
  import { fmtNumber } from '@/utils/format'
  import {
    buildCharsetRows,
    buildCredentialRows,
    buildLengthBars,
    buildPairBarRows,
    buildPasswordRows,
    fmtSuccessRate,
    type CredMetric,
  } from '@/utils/credentials'

  // Same 10s cadence as Overview/Activity: 4 polled queries = 24 req/min, well
  // under the 60/min per-IP API budget and decoupled from attack volume.
  const POLL_MS = 10_000
  const HERO_TOP_N = 12

  // The hero leaderboard is one endpoint with three "lenses". Pairs is the
  // botnet-fingerprint view; IP fan-out swaps the ranking to distinct source IPs
  // (distributed botnet vs lone brute-forcer); usernames collapses the password.
  type Mode = 'pairs' | 'fanout' | 'usernames' | 'passwords'
  const MODES = [
    { id: 'pairs', label: 'Pairs' },
    { id: 'fanout', label: 'IP fan-out' },
    { id: 'usernames', label: 'Usernames' },
    { id: 'passwords', label: 'Passwords' },
  ] as const
  const HERO_QUERIES = {
    pairs: { by: 'pair', metric: 'attempts' },
    fanout: { by: 'pair', metric: 'ip_fanout' },
    usernames: { by: 'username', metric: 'attempts' },
    passwords: { by: 'password', metric: 'attempts' },
  } as const

  const mode = ref<Mode>('pairs')
  const heroQuery = computed(() => ({ ...HERO_QUERIES[mode.value], top_n: HERO_TOP_N }))

  const heroQ = useQuery(
    computed(() => ({
      ...statsTopCredentialsOptions({ query: heroQuery.value }),
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  const outcomesQ = useQuery({ ...statsAuthOutcomesOptions(), refetchInterval: POLL_MS })
  const compositionQ = useQuery({ ...statsPasswordCompositionOptions(), refetchInterval: POLL_MS })
  const workedQ = useQuery({
    ...statsTopCredentialsOptions({ query: { by: 'pair', outcome: 'success', top_n: 5 } }),
    refetchInterval: POLL_MS,
  })

  await Promise.all([
    heroQ.suspense(),
    outcomesQ.suspense(),
    compositionQ.suspense(),
    workedQ.suspense(),
  ])

  const heroMetric = computed<CredMetric>(() =>
    mode.value === 'fanout' ? 'ip_fanout' : 'attempts',
  )
  const heroRows = computed(() => buildCredentialRows(heroQ.data.value ?? [], heroMetric.value))

  const outcomes = computed(() => outcomesQ.data.value!)
  const composition = computed(() => compositionQ.data.value!)
  const lengthBars = computed(() =>
    buildLengthBars(composition.value.lengths, composition.value.capped_at),
  )
  const charsetRows = computed(() => buildCharsetRows(composition.value.classes))
  const workedRows = computed(() => buildPairBarRows(workedQ.data.value ?? []))

  // Histogram drill-down: click a length bar to list its passwords. The query is
  // lazy (enabled only once a bar is selected) and never part of the initial
  // suspense, so the page paints without it.
  const selectedLength = ref<number | null>(null)
  const passwordsQ = useQuery(
    computed(() => ({
      ...statsPasswordsByLengthOptions({ query: { length: selectedLength.value ?? 0, top_n: 25 } }),
      enabled: selectedLength.value !== null,
      refetchInterval: POLL_MS,
      placeholderData: keepPreviousData,
    })),
  )
  const drillRows = computed(() => buildPasswordRows(passwordsQ.data.value ?? []))
  const selectedLabel = computed(() => {
    if (selectedLength.value === null) return ''
    return selectedLength.value >= composition.value.capped_at
      ? `${composition.value.capped_at}+`
      : String(selectedLength.value)
  })
  // Hide the tooltip on any view swap: the hovered trigger (a histogram bar /
  // hero row) unmounts during the transition without firing mouseleave, so the
  // bubble would otherwise stay frozen on screen.
  function selectLength(length: number): void {
    tt.hide()
    selectedLength.value = length
  }
  function clearLength(): void {
    tt.hide()
    selectedLength.value = null
  }
  function setMode(next: Mode): void {
    tt.hide()
    mode.value = next
  }

  const acceptRate = computed(() => fmtSuccessRate(outcomes.value.success_rate))
  const acceptedStyle = computed(() => {
    const { successful, total } = outcomes.value
    if (total <= 0) return { width: '0%' }
    // Floor a non-zero accepted slice to 2% so a rare success stays visible.
    return { width: `${Math.max(successful > 0 ? 2 : 0, (successful / total) * 100)}%` }
  })
  const splitLabel = computed(() => {
    const { successful, failed } = outcomes.value
    return `${fmtNumber(successful)} accepted, ${fmtNumber(failed)} rejected`
  })

  const tt = useTooltip()
</script>

<template>
  <div class="credentials">
    <PageHeader title="Credentials" />

    <section class="stats-grid" aria-label="Credential totals">
      <!-- Top row = credential vocabulary; bottom row = volume + outcome. -->
      <Card padding="sm">
        <Stat :value="fmtNumber(outcomes.unique_passwords)" label="Passwords" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(outcomes.unique_usernames)" label="Usernames" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(outcomes.total)" label="Attempts" />
      </Card>
      <Card padding="sm">
        <Stat :value="acceptRate" label="Accepted" />
      </Card>
    </section>

    <div class="body">
      <Card fill class="hero-pane">
        <template #title>
          <div class="hero-head">
            <h2 class="hero-title">Top credentials</h2>
            <div class="seg" role="group" aria-label="Leaderboard ranking">
              <button
                v-for="m in MODES"
                :key="m.id"
                type="button"
                class="seg-btn"
                :class="{ 'seg-btn-active': mode === m.id }"
                :aria-pressed="mode === m.id"
                @click="setMode(m.id)"
              >
                {{ m.label }}
              </button>
            </div>
          </div>
        </template>

        <div class="hero-body">
          <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
          <ul v-if="heroRows.length" class="cred-list" aria-label="Top attempted credentials">
            <li
              v-for="row in heroRows"
              :key="row.key"
              class="cred-row"
              @mouseenter="tt.show(row.title, $event)"
              @mousemove="tt.show(row.title, $event)"
              @mouseleave="tt.hide()"
            >
              <span class="cred-cred">
                <span class="cred-user" :class="{ 'cred-user-solo': !row.sub }">{{
                  row.label
                }}</span>
                <span v-if="row.sub" class="cred-pass">{{ row.sub }}</span>
              </span>
              <span class="cred-track" aria-hidden="true">
                <span class="cred-fill" :style="{ '--bar-w': row.widthPct }" />
              </span>
              <span class="cred-value" :class="{ 'cred-value-hot': row.emphasis }">
                {{ row.valueLabel }}
              </span>
            </li>
          </ul>
          <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
          <EmptyState v-else title="No credentials seen yet" />
        </div>
      </Card>

      <div class="side">
        <Card title="Outcomes" padding="sm">
          <div class="split" role="img" :aria-label="splitLabel">
            <span class="split-accepted" :style="acceptedStyle" />
          </div>
          <div class="split-legend">
            <span class="legend-accepted">{{ fmtNumber(outcomes.successful) }} accepted</span>
            <span>{{ fmtNumber(outcomes.failed) }} rejected</span>
          </div>
          <h3 class="side-sub">Credentials that worked</h3>
          <BarList
            :items="workedRows"
            label="Credentials cowrie accepted"
            empty-text="Nothing accepted yet"
          />
        </Card>

        <Card title="Password composition" padding="sm" class="comp-card" fill>
          <Transition name="comp-fade" mode="out-in">
            <!-- Default view: length histogram + charset breakdown. -->
            <div v-if="selectedLength === null" key="hist" class="comp-body">
              <div
                class="hist"
                role="group"
                aria-label="Password length distribution; activate a bar to list its passwords"
              >
                <div class="hist-bars">
                  <button
                    v-for="bar in lengthBars"
                    :key="bar.key"
                    type="button"
                    class="hist-col"
                    :disabled="bar.count === 0"
                    :aria-label="`Show the ${bar.count} passwords of ${bar.label || bar.length} characters`"
                    @click="selectLength(bar.length)"
                    @mouseenter="tt.show(bar.title, $event)"
                    @mousemove="tt.show(bar.title, $event)"
                    @mouseleave="tt.hide()"
                    @focus="tt.show(bar.title, $event)"
                    @blur="tt.hide()"
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

              <div class="comp-list">
                <BarList
                  :items="charsetRows"
                  label="Password character classes"
                  empty-text="No passwords yet"
                />
              </div>
            </div>

            <!-- Drill-down: the whole card becomes a scrollable list of the
                 passwords at the chosen length; size is fixed so nothing reflows. -->
            <div v-else key="drill" class="comp-drill">
              <div class="drill-head">
                <button type="button" class="back-btn" @click="clearLength">
                  <span aria-hidden="true">←</span> Composition
                </button>
                <span class="drill-title">{{ selectedLabel }} chars</span>
              </div>
              <div class="drill-scroll">
                <BarList
                  :items="drillRows"
                  label="Passwords of the selected length"
                  empty-text="No passwords of this length"
                />
              </div>
            </div>
          </Transition>
        </Card>
      </div>
    </div>

    <Tooltip v-bind="tt.state" />
  </div>
</template>

<style scoped>
  .credentials {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    flex: 1 1 auto;
    min-height: 0;
  }

  .stats-grid {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-3);
  }

  /* Body fills the viewport leftover (locked, no page scroll on desktop). Both
     columns stretch to that height; inside the side, the histogram stays a fixed
     dense height and the charset list spreads to fill, so nothing reads empty. */
  .body {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
    gap: var(--space-3);
  }

  .hero-pane {
    min-height: 0;
  }

  .hero-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    flex-wrap: wrap;
  }

  .hero-title {
    margin: 0;
    font-size: var(--type-lg);
    line-height: var(--type-lg-lh);
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
  }

  .seg {
    display: inline-flex;
    gap: 2px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 2px;
  }

  .seg-btn {
    border: 0;
    background: transparent;
    color: var(--text-muted);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 500;
    padding: 4px 10px;
    border-radius: calc(var(--radius-sm) - 1px);
    cursor: pointer;
    transition:
      color var(--motion-fast) ease,
      background var(--motion-fast) ease;
  }

  .seg-btn:hover {
    color: var(--text);
  }

  .seg-btn-active {
    background: var(--surface);
    color: var(--accent);
  }

  .seg-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .hero-body {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .cred-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: var(--space-2);
    flex: 1 1 auto;
    min-height: 0;
  }

  .cred-row {
    display: grid;
    /* Value is a fixed last column (not auto) so every row's bar starts and ends
       at the same x -- otherwise each row is its own grid and a longer value
       (e.g. "2 IPs" vs "1 IP") would stretch that row's bar out of line. */
    grid-template-columns: minmax(0, 1.3fr) minmax(60px, 1.4fr) 5rem;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
  }

  .cred-cred {
    display: flex;
    min-width: 0;
    font-family: var(--font-mono);
  }

  /* In Pairs mode the username is the (short) identity and stays full; the
     password sub takes the ellipsis. */
  .cred-user {
    flex: 0 0 auto;
    color: var(--text);
    white-space: nowrap;
  }

  /* In Usernames / Passwords mode the label IS the value (no sub) and can be a
     long string, so it must truncate instead of spilling across the bar track. */
  .cred-user-solo {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The password takes the ellipsis when a pair is too long to fit. */
  .cred-pass {
    flex: 0 1 auto;
    min-width: 0;
    color: var(--text-dim);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .cred-track {
    height: 6px;
    background: var(--bg-2);
    border-radius: 999px;
    overflow: hidden;
  }

  .cred-fill {
    display: block;
    height: 100%;
    width: var(--bar-w);
    background: var(--accent);
    border-radius: 999px;
    transition: width var(--motion-base) ease;
  }

  .cred-value {
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    text-align: right;
    white-space: nowrap;
  }

  /* High IP fan-out (botnet-distributed credential) -- gold, no layout shift. */
  .cred-value-hot {
    color: var(--warning);
    font-weight: 600;
  }

  .side {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
  }

  /* Fills the side column. Inside, the histogram is fixed (dense) and the
     charset list spreads to take the remaining height -- so the card fills with
     no empty gap, while the spiky histogram never stretches tall. */
  .comp-card {
    flex: 1 1 auto;
    min-height: 0;
  }

  .comp-card :deep(.card-body) {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .comp-body {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  /* Charset list takes the leftover height and distributes its rows to fill it.
     overflow-y:auto + scrollbar-gutter:stable reserve the same gutter the drill
     list reserves, so the two swap-states are exactly the same width (the list
     fits/spreads, so it never actually shows a scrollbar). */
  .comp-list {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .comp-list :deep(.bar-list) {
    flex: 1 1 auto;
    justify-content: space-between;
  }

  .comp-drill {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    /* Match the regular view's hist <-> charset gap (breathing room under the
       "<- Composition" header). */
    gap: var(--space-3);
  }

  /* Lock the count column to a fixed width in the composition lists so every
     row's bar track is identical and the bar right-edges line up (BarList's
     default trailing track is `auto`, which varies with the count's digits).
     Scoped, so Overview's BarLists are untouched. */
  .comp-list :deep(.bar-row),
  .drill-scroll :deep(.bar-row) {
    grid-template-columns: minmax(0, 1fr) minmax(60px, 2fr) 3.5rem;
  }
  .comp-list :deep(.bar-value),
  .drill-scroll :deep(.bar-value) {
    min-width: 0;
  }

  .drill-head {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .back-btn {
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    transition:
      color var(--motion-fast) ease,
      background var(--motion-fast) ease,
      border-color var(--motion-fast) ease;
  }

  .back-btn:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }

  .back-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .drill-title {
    font-family: var(--font-mono);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }

  /* Scrolls within the filled card (it can be up to 25 rows). Reserve the
     scrollbar gutter so the list width is the same whether it scrolls or not
     (and matches the non-scrolling charset list). */
  .drill-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  /* Cross-fade the two card states (out-in) so the swap reads as one surface
     changing, never as content jumping. */
  .comp-fade-enter-active,
  .comp-fade-leave-active {
    transition: opacity var(--motion-fast) ease;
    /* While a view fades out it stays in the DOM ~120ms. Without this, a
       mousemove over a leaving histogram bar re-fires the tooltip *after* the
       click hid it, freezing the bubble on screen. Make transitioning content
       inert so no stray hover events fire mid-swap. */
    pointer-events: none;
  }

  .comp-fade-enter-from,
  .comp-fade-leave-to {
    opacity: 0;
  }

  .split {
    display: flex;
    height: 10px;
    border-radius: 999px;
    overflow: hidden;
    background: color-mix(in srgb, var(--text-dim) 22%, transparent);
  }

  .split-accepted {
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
  }

  .split-legend {
    display: flex;
    justify-content: space-between;
    margin-top: var(--space-2);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .legend-accepted {
    color: var(--accent);
  }

  .side-sub {
    margin: var(--space-3) 0 var(--space-2);
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
  }

  /* Fixed, compact height: a dense little histogram. Letting it flex-grow made
     it a tall, mostly-empty chart with one lonely spike. The charset list below
     absorbs the leftover space so the card still fills. */
  .hist {
    flex: 0 0 auto;
    height: 180px;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .hist-bars {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    align-items: flex-end;
    gap: 2px;
  }

  .hist-col {
    flex: 1 1 0;
    height: 100%;
    display: flex;
    align-items: flex-end;
    /* button reset */
    border: 0;
    padding: 0;
    background: transparent;
    cursor: pointer;
  }

  .hist-col:disabled {
    cursor: default;
  }

  .hist-col:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  .hist-bar {
    width: 100%;
    background: var(--accent);
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    transition:
      height var(--motion-base) ease,
      background var(--motion-fast) ease;
  }

  .hist-col:hover:not(:disabled) .hist-bar {
    background: var(--accent-strong);
  }

  .hist-axis {
    display: flex;
    gap: 2px;
  }

  .hist-tick {
    flex: 1 1 0;
    text-align: center;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--text-dim);
    /* Labels can be wider than their thin cell ("16+"); let them spill into the
       adjacent (empty) cells instead of clipping. */
    overflow: visible;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* Pin the first/last axis labels to the histogram edges so the "16+" tail
     stays fully visible inside the card instead of being clipped at the edge. */
  .hist-tick:first-child {
    text-align: left;
  }
  .hist-tick:last-child {
    text-align: right;
  }

  @media (max-width: 768px) {
    /* The hero + two side cards can't all fit one short viewport; stack and let
     the page scroll (same play as Overview/Activity below md). */
    .credentials {
      overflow-y: auto;
    }
    /* Stack as a plain content-height flex column (not the desktop grid, whose
       definite height + min-height:0 let the hero shrink and clip its rows).
       Children below are flex:0 0 auto so they keep full height and the page
       scrolls. */
    .body {
      display: flex;
      flex-direction: column;
      flex: 0 0 auto;
    }
    .side {
      flex: 0 0 auto;
    }
    /* 2x2 grid (same play as ActivityView's 4 KPIs): two columns give each big
       number ~half the width, so "42.6%" fits comfortably with no clipping or
       sideways scroll. minmax(0,1fr) keeps the tracks shrinkable. */
    .stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    /* The 4-button toggle can't fit one row on a phone and a wrapping flex
       segmented control looks broken. Lay it out as a tidy full-width 2x2 grid
       (echoes the KPI 2x2 above). */
    .seg {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      width: 100%;
    }
    /* Hero: content-size so the whole list is displayed (no inner scroll) and
       the card is only as tall as its rows; the page scrolls. flex:0 0 auto
       keeps it from shrinking/clipping inside the flex column. */
    .body .hero-pane {
      flex: 0 0 auto;
      height: auto;
    }
    .body .hero-pane :deep(.card-body) {
      display: block;
    }
    .hero-body {
      height: auto;
    }
    .cred-list {
      justify-content: flex-start;
    }

    /* Composition: a fixed-height card so it stays the SAME size when you drill
       into the password list (matches the regular view). The desktop fill/scroll
       rules then run inside this fixed height -- charset spreads to fill, drill
       list scrolls -- so both states are identical in size, with no overflow. */
    .side .comp-card {
      flex: 0 0 auto;
      height: clamp(420px, 60vh, 560px);
    }
  }
</style>
