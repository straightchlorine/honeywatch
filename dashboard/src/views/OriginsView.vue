<script setup lang="ts">
  /**
   * Hex cartogram of source countries with their networks and SSH client/key-reuse breakdowns.
   */
  import { computed, onMounted, onUnmounted, ref } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useQuery } from '@tanstack/vue-query'
  import {
    statsCountriesOptions,
    statsAsnsOptions,
    statsSshClientsOptions,
    statsFingerprintsOptions,
    statsCountryDetailOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import StatTile from '@/components/base/StatTile.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import ChipButton from '@/components/base/ChipButton.vue'
  import InfoDot from '@/components/base/InfoDot.vue'
  import RankList, { type RankRow } from '@/components/base/RankList.vue'
  import CountryHive from '@/components/map/CountryHive.vue'
  import CountryDrawer from '@/components/map/CountryDrawer.vue'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { fmtNumber, fmtCompact, fmtRelativeTime } from '@/utils/format'
  import { cappedFracs } from '@/utils/cappedFracs'
  import { fmtSuccessRate } from '@/utils/credentials'
  import { WORLD_COUNTRY_COUNT } from '@/utils/countries'

  interface SshClientRow {
    client_version: string
    sessions: number
  }
  interface FingerprintRow {
    fingerprint: string
    fingerprint_type: string
    sessions: number
    ips: number
    first_seen: string
    last_seen: string
  }

  // Origins' aggregates barely move minute-to-minute; matches Overview's poll.
  const POLL_MS = 120_000

  const countriesQ = useQuery({
    ...statsCountriesOptions({ query: { sort: 'sessions', top_n: 100 } }),
    refetchInterval: POLL_MS,
  })
  const asnsQ = useQuery({
    ...statsAsnsOptions({ query: { top_n: 12 } }),
    refetchInterval: POLL_MS,
  })
  const sshClientsQ = useQuery({ ...statsSshClientsOptions(), refetchInterval: POLL_MS })
  const fingerprintsQ = useQuery({ ...statsFingerprintsOptions(), refetchInterval: POLL_MS })

  await Promise.all([
    countriesQ.suspense(),
    asnsQ.suspense(),
    sshClientsQ.suspense(),
    fingerprintsQ.suspense(),
  ])

  // '??' is the backend's Unknown-geo bucket (api/src/services/stats/common.py
  // UNKNOWN_COUNTRY) - it never gets a hex or a rank row here.
  const UNKNOWN_COUNTRY = '??'
  const resolvedCountries = computed(() =>
    (countriesQ.data.value?.countries ?? []).filter(
      (c) => !!c.country_code && c.country_code !== UNKNOWN_COUNTRY,
    ),
  )
  const totalCountries = computed(() => countriesQ.data.value?.total_countries ?? 0)
  const geoResolvedLabel = computed(() =>
    fmtSuccessRate(countriesQ.data.value?.geo_resolved_pct ?? null),
  )
  const sessionsShown = computed(() =>
    resolvedCountries.value.reduce((sum, c) => sum + c.sessions, 0),
  )
  const topCountry = computed(() => resolvedCountries.value[0])

  const sshClients = computed<SshClientRow[]>(
    () => (sshClientsQ.data.value as SshClientRow[] | undefined) ?? [],
  )
  const fingerprints = computed<FingerprintRow[]>(
    () => (fingerprintsQ.data.value as FingerprintRow[] | undefined) ?? [],
  )


  const netScale = computed(() => cappedFracs((asnsQ.data.value ?? []).map((a) => a.sessions)))
  const networkRows = computed<RankRow[]>(() => {
    const items = asnsQ.data.value ?? []
    return items.map((a) => {
      return {
        label: a.as_org ?? (a.asn !== null ? `AS${a.asn}` : 'Unknown network'),
        // The visible label is ellipsized, so the tooltip carries the full
        // operator name and AS number when the name is shown.
        title: [
          a.as_org ?? 'Unknown network',
          ...(a.as_org && a.asn !== null ? [`AS${a.asn}`] : []),
          `${fmtNumber(a.sessions)} sessions`,
          `${fmtNumber(a.distinct_ips)} address${a.distinct_ips === 1 ? '' : 'es'}`,
        ].join(' - '),
        value: fmtCompact(a.sessions),
        frac: netScale.value.frac(a.sessions),
        over: netScale.value.over(a.sessions),
      }
    })
  })

  const clientView = ref<'clients' | 'keys'>('clients')

  // URL is state: CountryDrawer's "Full intel" button links here with ?country=XX.
  const route = useRoute()
  const router = useRouter()
  const selectedCountry = computed({
    get: () => {
      const q = route.query.country
      return typeof q === 'string' && q ? q.toUpperCase() : null
    },
    set: (a2) => {
      const rest = { ...route.query }
      if (a2) rest.country = a2
      else delete rest.country
      void router.replace({ query: rest })
    },
  })

  // Drawer detail. `isPending` stays true for a disabled query (no fetch has
  // ever run), so it alone cannot drive the loading state - gate on selection.
  const countryQ = useQuery(
    computed(() => ({
      ...statsCountryDetailOptions({ path: { a2: selectedCountry.value ?? '' } }),
      enabled: !!selectedCountry.value,
    })),
  )
  const countryLoading = computed(() => !!selectedCountry.value && countryQ.isPending.value)

  function closeDrawer(): void {
    selectedCountry.value = null
  }

  // Escape clears the URL selection even if the drawer auto-closes.
  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && selectedCountry.value) closeDrawer()
  }
  onMounted(() => window.addEventListener('keydown', onKeydown))
  onUnmounted(() => window.removeEventListener('keydown', onKeydown))

  // Origins has no map, so a city click hands off to Overview's, which does.
  function showCityOnMap(p: { country_code?: string }): void {
    void router.push({ path: '/', query: p.country_code ? { country: p.country_code } : {} })
  }


  const TOOLTIP_CLIENTS =
    'The software attackers used to connect - most attacks reuse the same few programs.'
  const TOOLTIP_SPRAYED_KEYS =
    'Login keys offered in many attacks - the same key from many addresses points to one group behind them all.'

  const clientScale = computed(() => cappedFracs(sshClients.value.map((c) => c.sessions)))
  const clientRows = computed<RankRow[]>(() =>
    sshClients.value.map((c) => ({
      label: c.client_version,
      title: c.client_version,
      value: fmtCompact(c.sessions),
      frac: clientScale.value.frac(c.sessions),
      over: clientScale.value.over(c.sessions),
    })),
  )

  const keyScale = computed(() => cappedFracs(fingerprints.value.map((f) => f.sessions)))
  const keyRows = computed<RankRow[]>(() => {
    return fingerprints.value.map((f) => ({
      label: f.fingerprint,
      title: f.fingerprint,
      sub: `${fmtNumber(f.ips)} addresses - first seen ${fmtRelativeTime(f.first_seen)}, last seen ${fmtRelativeTime(f.last_seen)}`,
      value: fmtCompact(f.sessions),
      frac: keyScale.value.frac(f.sessions),
      over: keyScale.value.over(f.sessions),
    }))
  })
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="origins" />
    </template>

    <div class="origins">
      <div class="page-head">
        <h1>Origins</h1>
        <span class="sub">who is knocking, and from whose machines</span>
      </div>

      <div class="stat-row">
        <StatTile label="Countries seen" :value="fmtNumber(totalCountries)">
          <template #meta>
            <span>{{ fmtNumber(sessionsShown) }} sessions with a known country</span>
            <InfoDot
              title="Share of world"
              :text="`${((totalCountries / WORLD_COUNTRY_COUNT) * 100).toFixed(1)}% of ${WORLD_COUNTRY_COUNT} recognized countries`"
            />
          </template>
        </StatTile>
        <StatTile label="Located" :value="geoResolvedLabel">
          <template #meta>of sessions have a known country</template>
        </StatTile>
        <StatTile v-if="topCountry" label="Top origin" :value="fmtCompact(topCountry.sessions)">
          <template #meta>
            {{ useCountryFlag(topCountry.country_code) }} {{ topCountry.country }}
          </template>
        </StatTile>
      </div>

      <CountryDrawer
        :detail="countryQ.data.value ?? null"
        :loading="countryLoading"
        :show-full-intel="false"
        @close="closeDrawer"
        @fly-to-city="showCityOnMap"
      />

      <div class="grid-main">
        <div class="hive-wrapper">
          <CountryHive v-model:selected="selectedCountry" :countries="resolvedCountries" />
        </div>

        <div class="right-col">
          <HwCard title="Networks" note="top networks by session count">
            <RankList class="fill-list" :rows="networkRows" label-width="168px" />
          </HwCard>

          <HwCard title="Software used">
            <template #head-extra>
              <span class="toggle-row">
                <ChipButton :pressed="clientView === 'clients'" @toggle="clientView = 'clients'">
                  Clients
                  <template #trailing>
                    <InfoDot title="SSH clients" :text="TOOLTIP_CLIENTS" />
                  </template>
                </ChipButton>
                <ChipButton :pressed="clientView === 'keys'" @toggle="clientView = 'keys'">
                  Reused keys
                  <template #trailing>
                    <InfoDot title="Reused keys" :text="TOOLTIP_SPRAYED_KEYS" />
                  </template>
                </ChipButton>
              </span>
            </template>
            <RankList
              v-if="clientView === 'clients'"
              class="fill-list"
              :rows="clientRows"
              label-width="215px"
              mono
            />
            <RankList v-else class="fill-list" :rows="keyRows" label-width="215px" mono />
          </HwCard>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
  .origins {
    display: flex;
    flex-direction: column;
    gap: 14px;
    flex: 1 1 auto;
    min-height: 0;
  }

  .page-head {
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex: none;
  }

  .page-head h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.005em;
    color: var(--text);
  }

  .page-head .sub {
    color: var(--text-dim);
    font-size: 13px;
  }

  .page-head .spacer {
    flex: 1;
  }

  .stat-row {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    gap: 12px;
    flex: none;
  }

  .stat-row :deep(.meta) {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .grid-main {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    gap: 14px;
  }

  .hive-wrapper {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .right-col {
    display: grid;
    grid-template-rows: 1.1fr 1fr;
    gap: 14px;
    min-height: 0;
  }

  /* RankList defaults to content-sized (flex: 0 1 auto); grow it to the
     card's remaining height so its own overflow-y:auto is what scrolls, not
     the page. */
  .fill-list {
    flex: 1 1 auto;
    min-height: 0;
  }

  /* h2's uppercase/letter-spacing are inherited by default - reset them here
     so the toggle chip labels render as typed, not tracked caps. */
  .toggle-row {
    display: flex;
    gap: 6px;
    margin-left: auto;
    text-transform: none;
    letter-spacing: normal;
    flex-wrap: wrap;
    align-items: center;
  }

  .toggle-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  @media (max-width: 900px) {
    .page-head {
      flex-wrap: wrap;
      row-gap: 8px;
    }

    .stat-row {
      grid-auto-flow: row;
      grid-template-columns: 1fr 1fr;
    }

    .grid-main {
      display: flex;
      flex-direction: column;
    }

    .hive-legend {
      flex-wrap: wrap;
      justify-content: center;
    }

    .right-col {
      display: flex;
      flex-direction: column;
    }

    .right-col :deep(.card) {
      max-height: 340px;
    }
  }
</style>
