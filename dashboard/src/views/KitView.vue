<script setup lang="ts">
  // Dev-only component; not routed in production.
  import { ref } from 'vue'
  import HwCard from '@/components/base/HwCard.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import ChipButton from '@/components/base/ChipButton.vue'
  import ChipSelect from '@/components/base/ChipSelect.vue'
  import HwBadge from '@/components/base/HwBadge.vue'
  import SeqLegend from '@/components/base/SeqLegend.vue'
  import InsightNote from '@/components/base/InsightNote.vue'
  import HexIcon from '@/components/base/HexIcon.vue'
  import RankList, { type RankRow } from '@/components/base/RankList.vue'
  import Sparkline from '@/components/charts/Sparkline.vue'
  import MeterBar from '@/components/charts/MeterBar.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import PageShell from '@/components/layout/PageShell.vue'

  const pressed = ref(false)
  const sortValue = ref('sessions')

  const rankRows: RankRow[] = [
    { label: 'China', value: '34,468', frac: 1, icon: 'CN', badge: '1.4%', badgeClass: 'amber' },
    { label: 'United States', value: '12,004', frac: 0.35, icon: 'US' },
    { label: 'Russia', value: '8,221', frac: 0.24, icon: 'RU', sub: 'AS45102 - Alibaba Cloud' },
  ]
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="overview" />
    </template>

    <h1>Kit demo (dev only)</h1>

    <section class="row">
      <StatTile label="Sessions" value="344,019" :spark="[3, 5, 4, 8, 6, 9, 7]">
        <template #meta>3.16% accepted</template>
      </StatTile>
      <StatTile label="Unique IPs" value="1,204" glass />
    </section>

    <HwCard title="Rank list" note="top 3">
      <RankList :rows="rankRows" />
    </HwCard>

    <section class="row">
      <ChipButton :pressed="pressed" @toggle="pressed = !pressed">Toggle</ChipButton>
      <ChipSelect
        v-model="sortValue"
        label="Sort by"
        :options="[
          { value: 'sessions', label: 'Sessions' },
          { value: 'ips', label: 'Unique IPs' },
        ]"
      />
      <HwBadge tone="ok">accepted</HwBadge>
      <HwBadge tone="bad">rejected</HwBadge>
      <HwBadge tone="amber">1.4%</HwBadge>
      <HwBadge tone="dim">n/a</HwBadge>
      <HexIcon :size="24" filled />
      <HexIcon :size="24" />
      <Sparkline :values="[3, 5, 4, 8, 6, 9, 7]" />
      <MeterBar :frac="0.0316" />
    </section>

    <SeqLegend min="1" max="37K" none-label="none" />

    <InsightNote>Evenings are <b>1.5x</b> more active than weekend mornings.</InsightNote>
  </PageShell>
</template>

<style scoped>
  .row {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }
</style>
