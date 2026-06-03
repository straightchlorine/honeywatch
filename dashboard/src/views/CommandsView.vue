<script setup lang="ts">
  import { computed } from 'vue'
  import { useQuery } from '@tanstack/vue-query'
  import { statsCommandsOptions } from '@/api/queries'
  import Card from '@/components/base/Card.vue'
  import Stat from '@/components/base/Stat.vue'
  import BarList from '@/components/base/BarList.vue'
  import PageHeader from '@/components/base/PageHeader.vue'
  import { fmtNumber } from '@/utils/format'
  import { buildCommandRows, buildTacticRows, buildCommandLineRows } from '@/utils/commands'

  // Commands are a slow-moving aggregate; poll on the same 10s cadence as the
  // other pages (well under the per-IP API rate limit).
  const POLL_MS = 10_000
  const commandsQ = useQuery({
    ...statsCommandsOptions({ query: { top_n: 15 } }),
    refetchInterval: POLL_MS,
  })
  // Suspense at setup: a load failure rejects here and bubbles to the App-level
  // ErrorBoundary outside <Suspense> (same pattern as the other views).
  await commandsQ.suspense()

  const data = computed(() => commandsQ.data.value!)
  const commandRows = computed(() => buildCommandRows(data.value.top_commands))
  const tacticRows = computed(() => buildTacticRows(data.value.tactics))
  const lineRows = computed(() => buildCommandLineRows(data.value.top_lines))
  // A poll failure keeps the last good data on screen; flag it politely.
  const isStale = computed(() => commandsQ.isError.value)
</script>

<template>
  <div class="commands">
    <PageHeader title="Commands" sub="What attackers ran once they reached a shell" />
    <p v-if="isStale" class="stale" role="status">Showing the last good data — refetching.</p>

    <section class="stats-grid" aria-label="Command totals">
      <Card padding="sm">
        <Stat :value="fmtNumber(data.active_sessions)" label="Active sessions" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(data.unique_commands)" label="Unique commands" />
      </Card>
      <Card padding="sm">
        <Stat :value="fmtNumber(data.total_commands)" label="Total commands" />
      </Card>
    </section>

    <div class="body">
      <Card fill title="Top commands">
        <div class="scroll">
          <BarList
            :items="commandRows"
            label="Top commands by frequency"
            empty-text="No commands yet"
          />
        </div>
      </Card>

      <Card fill title="Tactics">
        <div class="scroll">
          <BarList
            :items="tacticRows"
            label="Commands grouped by attacker tactic"
            empty-text="No commands yet"
          />
        </div>
      </Card>

      <Card fill title="Attack scripts">
        <div class="scroll">
          <BarList
            :items="lineRows"
            label="Most common chained one-liners"
            empty-text="No multi-step scripts yet"
          />
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
  .commands {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    /* Fill the shell column so the .body grid flexes to the leftover height and
       the page fits the viewport without scrolling on desktop. */
    flex: 1 1 auto;
    min-height: 0;
  }

  .stale {
    flex: 0 0 auto;
    margin: 0;
    font-size: var(--type-xs);
    line-height: var(--type-xs-lh);
    color: var(--warning);
  }

  .stats-grid {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--space-3);
  }

  .body {
    flex: 1 1 auto;
    min-height: 0;
    display: grid;
    /* commands | tactics | attack scripts (scripts widest — long one-liners). */
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr) minmax(0, 1.4fr);
    gap: var(--space-3);
  }

  /* Each card fills its column; the bar list scrolls inside so the page itself
     never scrolls on desktop (the viewport-fit rule). */
  .scroll {
    height: 100%;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  @media (max-width: 768px) {
    /* Stop hard-fitting: let the page scroll and each pane render in full — the
       proven mobile recipe from Credentials / Countries. */
    .commands {
      overflow-y: auto;
    }
    .body {
      display: flex;
      flex-direction: column;
      flex: 0 0 auto;
    }
    .body > :deep(.card) {
      flex: 0 0 auto;
    }
    /* Un-trap the fill cards: lay them out at content height and let the page
       (not the inner pane) scroll. */
    .body :deep(.card-fill .card-body) {
      display: block;
    }
    .scroll {
      height: auto;
      overflow: visible;
    }
  }
</style>
