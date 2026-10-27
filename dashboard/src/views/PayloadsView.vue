<script setup lang="ts">
  /**
   * Payloads: captured files as "specimens". Backend has no "kind" field
   * (miner/botnet/dropper), so kind filter is omitted to avoid UI controls without data.
   */
  import { computed, nextTick, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
  import { useQuery } from '@tanstack/vue-query'
  import { RouterLink, useRoute } from 'vue-router'
  import {
    statsDownloadsOptions,
    statsTcpipDestinationsOptions,
    statsOutcomesOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import { suspenseAll } from '@/api/queries'
  import type { PayloadDownloadResponse, TcpipDestinationResponse } from '@/api/generated/types.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import { benignContent, vtUrl } from '@/utils/knownDigests'
  import StatTile from '@/components/base/StatTile.vue'
  import InfoDot from '@/components/base/InfoDot.vue'
  import RankList, { type RankRow } from '@/components/base/RankList.vue'
  import InsightNote from '@/components/base/InsightNote.vue'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { countryDisplayName } from '@/utils/countries'
  import { fmtNumber, fmtRelativeTime } from '@/utils/format'
  import { ICONS } from '@/components/icons'
  import { cappedFracs } from '@/utils/cappedFracs'

  const tt = useHwTooltip()

  // Fade indicator when the list is cut off by scroll height.
  const specimensEl = useTemplateRef<HTMLElement>('specimensEl')
  function checkSpecimens(): void {
    const n = specimensEl.value
    if (n) n.classList.toggle('has-more', n.scrollTop + n.clientHeight < n.scrollHeight - 4)
  }
  const specimensRo = new ResizeObserver(checkSpecimens)
  onMounted(() => {
    checkSpecimens()
    if (specimensEl.value) specimensRo.observe(specimensEl.value)
  })
  onUnmounted(() => specimensRo.disconnect())

  // Roving tabindex (ARIA grid, as CountryHive): the specimens are ONE Tab stop - the cell last
  // focused, else the first link. Rows = specimens, cells = card link + VirusTotal link.
  const tabSha = ref<string | null>(null)
  const tabCol = ref(0)
  const tabStop = computed(() => {
    const hit = downloads.value.some((d) => d.sha256 === tabSha.value)
    return {
      sha: hit ? tabSha.value : downloads.value[0]?.sha256,
      col: hit ? tabCol.value : 0,
    }
  })
  function tabAt(sha: string, col: number): 0 | -1 {
    return sha === tabStop.value.sha && col === tabStop.value.col ? 0 : -1
  }
  function onSpecFocus(sha: string, e: FocusEvent): void {
    const row = (e.currentTarget as HTMLElement).closest('li')!
    tabSha.value = sha
    tabCol.value = Math.max(
      0,
      [...row.querySelectorAll('a')].indexOf(e.target as HTMLAnchorElement),
    )
  }
  function onSpecKeydown(e: KeyboardEvent): void {
    if (e.altKey || e.metaKey) return
    const row = (e.currentTarget as HTMLElement).closest('li')!
    // Rows hidden by the phone's 8-row cap are not walkable.
    const rows = [...specimensEl.value!.querySelectorAll<HTMLElement>('li.spec')].filter(
      (r) => getComputedStyle(r).display !== 'none',
    )
    const links = (r: HTMLElement) => [...r.querySelectorAll<HTMLElement>('a')]
    const col = Math.max(0, links(row).indexOf(e.target as HTMLElement))
    const i = rows.indexOf(row)
    let r = i
    let c = col
    switch (e.key) {
      case 'ArrowDown':
        r = Math.min(i + 1, rows.length - 1)
        break
      case 'ArrowUp':
        r = Math.max(i - 1, 0)
        break
      case 'ArrowRight':
        c = col + 1
        break
      case 'ArrowLeft':
        c = col - 1
        break
      case 'Home':
        if (e.ctrlKey) r = 0
        c = 0
        break
      case 'End':
        if (e.ctrlKey) r = rows.length - 1
        c = 9
        break
      default:
        return
    }
    e.preventDefault()
    const to = links(rows[r]!)
    to[Math.min(Math.max(c, 0), to.length - 1)]?.focus()
  }

  function jumpToRelay(): void {
    const t = document.getElementById('relay-card')
    t?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    t?.focus({ preventScroll: true })
  }

  // Deep link: scroll to #spec-<sha>. :target cannot match (the list renders after navigation),
  // so the template marks it with .picked. Only the top-N specimens render; a hash for any other sha does nothing.
  const route = useRoute()
  const hash = computed(() => route.hash)
  function scrollToPicked(): void {
    if (hash.value.startsWith('#spec-'))
      document.getElementById(hash.value.slice(1))?.scrollIntoView({ block: 'center' })
  }
  onMounted(scrollToPicked)
  watch(hash, () => nextTick(scrollToPicked))

  const POLL_MS = 60_000
  const SPECIMEN_TOP_N = 50
  const RELAY_TOP_N = 12

  const downloadsQ = useQuery({
    ...statsDownloadsOptions({ query: { top_n: SPECIMEN_TOP_N } }),
    refetchInterval: POLL_MS,
  })
  const tcpipQ = useQuery({
    ...statsTcpipDestinationsOptions({ query: { top_n: RELAY_TOP_N } }),
    refetchInterval: POLL_MS,
  })
  // COUNT(*) FILTER: avoids double-counting sessions with multiple files/networks.
  const outcomesQ = useQuery({ ...statsOutcomesOptions(), refetchInterval: POLL_MS })

  await suspenseAll(downloadsQ, tcpipQ, outcomesQ)

  const downloads = computed<PayloadDownloadResponse[]>(() => downloadsQ.data.value ?? [])

  // Phones list 8 specimens (CSS) until "Show all"; a deep-linked specimen is always kept.
  const NARROW_LIST = 8
  const showAll = ref(false)
  // The button unmounts on click, so hand focus to the first row it revealed.
  async function revealAll(): Promise<void> {
    showAll.value = true
    await nextTick()
    const rows = specimensEl.value?.querySelectorAll<HTMLElement>('li.spec')
    rows?.[NARROW_LIST]?.querySelector<HTMLElement>('.spec-link')?.focus()
  }
  const tcpip = computed<TcpipDestinationResponse[]>(() => tcpipQ.data.value ?? [])

  // KPIs: four questions a specimen card cannot answer, so nothing on the row is printed twice.
  const outcomes = computed(() => outcomesQ.data.value ?? null)
  const specimenCount = computed(() => downloads.value.length)
  const captureCount = computed(() => downloads.value.reduce((sum, d) => sum + d.sessions, 0))
  const singletonCount = computed(() => downloads.value.filter((d) => d.sessions === 1).length)

  /** "1 in N", or '' when the divisor is missing or zero. */
  function oneIn(part: number | undefined, whole: number | undefined): string {
    if (!part || !whole) return ''
    return `1 in ${fmtNumber(Math.round(whole / part))}`
  }

  const fetchedLabel = computed(() => (outcomes.value ? fmtNumber(outcomes.value.downloads) : '-'))
  const fetchedRatio = computed(() => oneIn(outcomes.value?.downloads, outcomes.value?.shell))
  const fetchedMeta = computed(() =>
    fetchedRatio.value
      ? `${fetchedRatio.value} of the ${fmtNumber(outcomes.value?.shell)} that got control`
      : '',
  )
  const relayLabel = computed(() => (outcomes.value ? fmtNumber(outcomes.value.tcpip) : '-'))
  const relayRatio = computed(() => oneIn(outcomes.value?.tcpip, outcomes.value?.total))
  const relayMeta = computed(() =>
    relayRatio.value ? `${relayRatio.value} - the honeypot blocked every one` : '',
  )

  /** Inclusive span of the shelf, not of the honeypot's uptime. */
  const span = computed(() => {
    const first = downloads.value
      .map((d) => d.first_seen)
      .filter(Boolean)
      .sort()[0]
    const last = downloads.value
      .map((d) => d.last_seen)
      .filter(Boolean)
      .sort()
      .at(-1)
    return first && last ? { first, last } : null
  })
  const windowLabel = computed(() => {
    if (!span.value) return '-'
    const { first, last } = span.value
    // Calendar days, not elapsed hours: the meta line names two DATES, so a
    // span half a day short would print "87 days" under "May 31 to Aug 27".
    const day = (iso: string) => Math.floor(new Date(iso).getTime() / 86_400_000)
    const days = day(last) - day(first)
    return days < 1 ? 'one day' : `${fmtNumber(days)} days`
  })
  const windowMeta = computed(() => {
    if (!span.value) return ''
    const { first, last } = span.value
    return `${fmtShortDate(first)} to ${fmtShortDate(last)}, newest ${fmtRelativeTime(last)}`
  })
  const windowShort = computed(() =>
    span.value ? `${fmtShortDate(span.value.first)} - ${fmtShortDate(span.value.last)}` : '',
  )

  function shaPrefix(sha: string): string {
    return sha.slice(0, 12)
  }

  /** Sessions well above machines means one operator fetching over and over. */
  function repeated(d: PayloadDownloadResponse): boolean {
    return d.machines > 0 && d.sessions / d.machines >= 2
  }

  /**
   * Route to sessions that captured this payload. SessionsView auto-expands
   * single-row lists, so no explicit `open` parameter is needed.
   */
  function sessionsFor(d: PayloadDownloadResponse) {
    return { name: 'sessions', query: { sha256: d.sha256 } }
  }

  /**
   * Accessible label for card link. Tooltip lacks role and aria-live, so
   * all visual content must be in the link text.
   */
  function cardLabel(d: PayloadDownloadResponse): string {
    const what = benignContent(d.sha256)
    const origin = d.countries.length ? ` from ${countryLabel(d.countries)}` : ''
    const shape =
      d.sessions > 1
        ? `${fmtNumber(d.sessions)} sessions from ${fmtNumber(d.machines)} machines${origin}`
        : `seen once, on ${fmtShortDate(d.first_seen)}${origin}`
    return (
      `Sessions for ${shaPrefix(d.sha256)}: ${shape}.` +
      (what ? ` Not malware: this capture is ${what}.` : '')
    )
  }

  /** Tooltip for origin flags: top 3 countries. */
  function originLabel(d: PayloadDownloadResponse): string {
    return d.countries.length
      ? `Fetched from ${countryLabel(d.countries)}`
      : 'Origin could not be resolved'
  }
  function flagsFor(codes: string[]): string {
    return codes.length ? codes.map((c) => useCountryFlag(c)).join(' ') : '-'
  }
  function countryLabel(codes: string[]): string {
    return codes.length ? codes.map((c) => countryDisplayName(c)).join(', ') : 'Unknown origin'
  }
  function fmtShortDate(iso: string | null): string {
    if (!iso) return '-'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '-'
    return d.toLocaleDateString('en', { month: 'short', day: '2-digit', timeZone: 'UTC' })
  }

  // Interpret the port, never the attacker's intent.
  const PORT_SERVICES: Record<number, string> = {
    20: 'FTP data',
    21: 'FTP',
    22: 'SSH',
    23: 'Telnet',
    25: 'SMTP',
    53: 'DNS',
    80: 'HTTP',
    110: 'POP3',
    143: 'IMAP',
    443: 'HTTPS',
    445: 'SMB',
    465: 'SMTPS',
    587: 'SMTP submission',
    2525: 'SMTP (alt)',
    993: 'IMAPS',
    995: 'POP3S',
    1433: 'MSSQL',
    1723: 'PPTP',
    2323: 'Telnet (alt)',
    3306: 'MySQL',
    3389: 'RDP',
    3478: 'STUN',
    4444: 'Metasploit handler',
    5060: 'SIP',
    5900: 'VNC',
    6379: 'Redis',
    6667: 'IRC',
    8080: 'HTTP (alt)',
    8443: 'HTTPS (alt)',
    9200: 'Elasticsearch',
    27017: 'MongoDB',
  }
  function portService(port: number): string {
    return PORT_SERVICES[port] ?? `Port ${port}`
  }
  // Mail ports mark relay probes.
  const MAIL_PORTS = new Set([25, 465, 587, 2525])
  /** Classify by port number, not outcome label, so renaming a label can never flip the badge color. */
  function portBadgeClass(port: number): RankRow['badgeClass'] {
    if (MAIL_PORTS.has(port)) return 'bad'
    if (port === 53 || port === 3478) return 'dim'
    return 'amber'
  }

  const relayRows = computed<RankRow[]>(() => {
    const { frac } = cappedFracs(tcpip.value.map((t) => t.sessions))
    return tcpip.value.map((t) => {
      const net = t.network ?? 'Unknown network'
      const where = t.country_code
        ? useCountryFlag(t.country_code)
        : t.country
          ? t.country
          : 'no fixed location'
      return {
        label: net,
        title: `${net}, port ${t.port} (${portService(t.port)}) - ${fmtNumber(t.sessions)} sessions from ${fmtNumber(t.hosts)} addresses, ${t.country ?? 'no fixed location'}`,
        value: fmtNumber(t.sessions),
        frac: frac(t.sessions),
        badge: String(t.port),
        badgeClass: portBadgeClass(t.port),
        badgeTitle: portService(t.port),
        sub: `${portService(t.port)} \u00b7 ${fmtNumber(t.hosts)} host${t.hosts === 1 ? '' : 's'} \u00b7 ${where}`,
      }
    })
  })

  const relayInsight = computed(() => {
    const mail = tcpip.value.filter((t) => MAIL_PORTS.has(t.port))
    if (!mail.length) return ''
    const reqs = mail.reduce((sum, t) => sum + t.sessions, 0)
    return (
      `${fmtNumber(reqs)} of these requests target mail ports - the honeypot is being tested ` +
      'as a relay, not browsed.'
    )
  })
</script>

<template>
  <PageShell>
    <template #head>
      <TopBar current="payloads" />
    </template>

    <div class="payloads">
      <div class="page-head">
        <h1>Payloads</h1>
        <span class="sub"
          ><span class="m-full"
            >what they leave behind - every file written to the honeypot is saved here</span
          ><span class="m-short">every file attackers leave behind</span></span
        >
      </div>

      <section class="stat-row" aria-label="Totals">
        <StatTile label="Sessions that fetched a file" short="Got a file" :value="fetchedLabel">
          <template #label-extra>
            <InfoDot
              title="Sessions that fetched a file"
              :text="`Sessions that downloaded at least one file. A session that fetched two files still counts once.${fetchedMeta ? ` That is ${fetchedMeta}.` : ''}`"
            />
          </template>
          <template #meta>
            <span class="m-full">{{ fetchedMeta }}</span>
            <span class="m-short">{{ fetchedRatio && `${fetchedRatio} sessions` }}</span>
          </template>
        </StatTile>
        <StatTile label="Files kept" :value="fmtNumber(specimenCount)">
          <template #label-extra>
            <InfoDot
              title="Files kept"
              :text="`Different files, each counted once. Two harmless leftovers - a blank line, and the text admin:admin - are included because attackers really wrote them. ${fmtNumber(singletonCount)} were seen only once. ${fmtNumber(captureCount)} fetches across the files shown, counting each session once per file.`"
            />
          </template>
          <template #meta>
            <span class="m-full"
              >{{ fmtNumber(singletonCount) }} seen only once &middot;
              {{ fmtNumber(captureCount) }} fetches in all</span
            >
            <span class="m-short">{{ fmtNumber(singletonCount) }} seen once</span>
          </template>
        </StatTile>
        <StatTile label="Date range" :value="windowLabel">
          <template #label-extra>
            <InfoDot
              title="Date range"
              :text="`First file to most recent. The honeypot has been running longer - this is only the span the files cover.${windowMeta ? ` ${windowMeta}.` : ''}`"
            />
          </template>
          <template #meta>
            <span class="m-full">{{ windowMeta }}</span>
            <span class="m-short">{{ windowShort }}</span>
          </template>
        </StatTile>
        <StatTile label="Sessions that tried to relay" short="Relay attempts" :value="relayLabel">
          <template #label-extra>
            <InfoDot
              title="Sessions that tried to relay"
              :text="`Sessions that asked the honeypot to forward a connection elsewhere. The honeypot blocked every one. Counted once per session.${relayRatio ? ` That is ${relayRatio} of all sessions.` : ''}`"
            />
          </template>
          <template #meta>
            <span class="m-full">{{ relayMeta }}</span>
            <span class="m-short">{{ relayRatio && `${relayRatio} sessions` }}</span>
          </template>
        </StatTile>
      </section>

      <a class="relay-jump" href="#relay-card" @click.prevent="jumpToRelay"
        ><span class="relay-jump-text"
          >Relay attempts<small>{{ tcpip.length }} networks they tried to reach</small></span
        ><svg class="relay-jump-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path :d="ICONS['chevron-right']" fill="currentColor" /></svg
      ></a>

      <div class="grid-main">
        <HwCard class="spec-card" title="Specimens" :note="`${specimenCount} files kept`">
          <ul
            ref="specimensEl"
            class="specimens"
            :class="{ expanded: showAll }"
            role="grid"
            aria-label="Captured files"
            @scroll.passive="checkSpecimens"
          >
            <!-- keys bubble from the roving links; the row itself is never focused -->
            <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -->
            <li
              v-for="d in downloads"
              :id="'spec-' + d.sha256"
              :key="d.sha256"
              :class="{ recurring: d.sessions > 1, picked: hash === '#spec-' + d.sha256 }"
              class="spec"
              role="row"
              @keydown="onSpecKeydown"
            >
              <span class="cell" role="gridcell">
                <RouterLink
                  class="spec-link"
                  :to="sessionsFor(d)"
                  :tabindex="tabAt(d.sha256, 0)"
                  @focus="onSpecFocus(d.sha256, $event)"
                >
                  <span class="mono head-sha" aria-hidden="true">{{ shaPrefix(d.sha256) }}</span>
                  <span class="visually-hidden">{{ cardLabel(d) }}</span>
                </RouterLink>
              </span>
              <span
                class="flags"
                role="gridcell"
                aria-hidden="true"
                @pointerenter="tt.show(originLabel(d))"
                @pointermove="tt.move($event)"
                @pointerleave="tt.hide()"
                >{{ flagsFor(d.countries) }}</span
              >
              <span class="cell" role="gridcell">
                <span v-if="benignContent(d.sha256)" class="benign">not malware</span>
                <a
                  v-else
                  class="vt"
                  :href="vtUrl(d.sha256)"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open on VirusTotal"
                  :tabindex="tabAt(d.sha256, 1)"
                  @focus="onSpecFocus(d.sha256, $event)"
                  >VirusTotal</a
                >
              </span>
              <p class="fact" role="gridcell">
                <template v-if="d.sessions > 1">
                  <b class="num">{{ fmtNumber(d.sessions) }}</b> sessions from
                  <template v-if="repeated(d)">just </template>
                  <b class="num">{{ fmtNumber(d.machines) }}</b>
                  {{ d.machines === 1 ? 'machine' : 'machines' }}.
                </template>
                <template v-else>
                  Seen once, on <b>{{ fmtShortDate(d.first_seen) }}</b
                  >.
                </template>
              </p>
            </li>
            <li v-if="!downloads.length" class="empty" role="row">
              <span class="cell" role="gridcell">No files captured yet.</span>
            </li>
            <li v-if="!showAll && downloads.length > NARROW_LIST" class="show-all" role="row">
              <span class="cell" role="gridcell">
                <button type="button" @click="revealAll">
                  Show all {{ downloads.length }}
                </button>
              </span>
            </li>
          </ul>
        </HwCard>

        <div class="right-col">
          <HwCard
            title="Relay attempts"
            :note="`top ${tcpip.length} networks attackers tried to reach`"
            id="relay-card"
            tabindex="-1"
            class="relay-card"
          >
            <RankList class="relay-rank" :rows="relayRows" label-width="150px" badge-width="46px" />
            <p v-if="!tcpip.length" class="empty">No relay attempts recorded yet.</p>
            <InsightNote v-if="relayInsight" class="relay-insight">{{ relayInsight }}</InsightNote>
          </HwCard>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<style scoped>
  .payloads {
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

  .page-head .sub {
    color: var(--text-dim);
    font-size: 13px;
  }

  .stat-row {
    flex: none;
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: 1fr;
    gap: 12px;
  }

  .m-short {
    display: none;
  }

  @media (max-width: 480px) {
    .stat-row :deep(.value) {
      font-size: 22px;
    }

    .m-full {
      display: none;
    }

    .m-short {
      display: inline;
    }
  }

  .grid-main {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
    gap: 14px;
  }

  .spec-card {
    min-height: 0;
  }

  .cell {
    display: contents;
  }

  /* Relay rows: the sub-line sits tight under its name, rows stay 8px apart. */
  .relay-rank :deep(.rank-list) {
    gap: 8px;
  }

  .relay-rank :deep(.rank-row) {
    row-gap: 0;
  }

  .relay-rank :deep(.rk-sub) {
    margin-top: 0;
    line-height: 16px;
  }

  /* Desktop only: rows share the card height evenly down to the mail-port note,
     and the port pills take the protocol colours (web amber, DNS/STUN muted,
     mail red). Phone keeps the plain list above. */
  @media (min-width: 901px) {
    .relay-rank :deep(.rank-list) {
      flex: 1 1 0;
      gap: 0;
    }

    .relay-rank :deep(.rank-row) {
      flex: 1 1 0;
      min-height: 38px;
      align-content: center;
    }

    .relay-rank :deep(.rk-badge) {
      justify-self: end;
    }

    .relay-rank :deep(.rk-track) {
      height: 6px;
      border-radius: 3px;
      background: var(--border);
    }

    .relay-rank :deep(.rk-fill) {
      min-width: 6px;
      border-radius: 3px;
    }

    .relay-rank :deep(.rk-sub) {
      font-family: var(--font-mono);
      color: var(--text-muted);
    }

    .relay-rank :deep(.badge) {
      padding: 2px 9px;
    }

    .relay-rank :deep(.badge.amber) {
      color: var(--accent-hot);
      background: color-mix(in srgb, var(--accent) 14%, transparent);
      border-color: var(--accent-dim);
    }

    .relay-rank :deep(.badge.dim) {
      color: var(--text-muted);
      background: var(--surface);
      border-color: var(--border-strong);
    }

    .relay-rank :deep(.badge.bad) {
      color: var(--bad);
      background: color-mix(in srgb, var(--bad) 12%, transparent);
      border-color: color-mix(in srgb, var(--bad) 45%, var(--bg-1));
    }

    /* Doubled class beats the base margin-top:auto; the list now fills the card. */
    .relay-card .relay-insight {
      margin-top: 12px;
    }
  }

  .specimens {
    list-style: none;
    margin: 0;
    padding: 8px 4px 10px 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    /* Fixed row height, not 1fr: 1fr divides available space evenly, squeezing
       and clipping cards once there are more rows than fit on screen. */
    grid-auto-rows: 58px;
    align-content: start;
    gap: 12px;
    overflow-y: auto;
    min-height: 0;
    flex: 1 1 auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border-strong) transparent;
    scrollbar-gutter: stable;
  }

  /* Taller viewports have slack the fixed 58px card cannot absorb, so it goes
     into the rhythm rather than into one dead band at the bottom. */
  @media (min-height: 1000px) {
    .specimens {
      row-gap: 20px;
    }
  }

  .specimens.has-more {
    mask-image: linear-gradient(#000 calc(100% - 22px), transparent);
  }

  /* Constant card height is load-bearing: layout fits viewport without scroll. */
  .spec {
    position: relative;
    isolation: isolate;
    height: 58px;
    box-sizing: border-box;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 8px 12px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-content: center;
    column-gap: 8px;
    row-gap: 2px;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
    transition:
      border-color var(--motion-fast),
      background var(--motion-fast);
  }

  .spec:hover,
  .spec:focus-within,
  .spec.picked {
    border-color: var(--accent-dim);
    background: var(--surface-hover);
  }

  /* Honeycomb pattern signals repeated specimens. Needs .spec's isolation:
     isolate to scope this z-index to the card, not the whole page. */
  .spec.recurring::after {
    content: '';
    position: absolute;
    right: -14px;
    top: -14px;
    width: 78px;
    height: 78px;
    z-index: -1;
    background: radial-gradient(circle at 100% 0%, var(--accent) 0, transparent 72%);
    opacity: 0.26;
    -webkit-mask: var(--comb) repeat;
    mask: var(--comb) repeat;
    -webkit-mask-size: 14px 24px;
    mask-size: 14px 24px;
    pointer-events: none;
  }

  /* Pseudo-element hit-area keeps card children as siblings (valid HTML/a11y);
     focus ring outlines card, not just the hash. */
  .spec-link {
    grid-column: 1;
    grid-row: 1;
    text-decoration: none;
    color: inherit;
    min-width: 0;
  }

  .spec-link::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
  }

  .spec-link:focus-visible {
    outline: none;
  }

  .spec-link:focus-visible::before {
    outline: 2px solid var(--accent);
    outline-offset: -3px;
  }

  .spec .head-sha {
    font: 650 12.5px var(--font-mono);
    letter-spacing: 0.01em;
    color: var(--text);
  }

  .spec .flags {
    grid-column: 2;
    grid-row: 1;
    position: relative;
    justify-self: start;
    max-width: 100%;
    font-size: 11px;
    line-height: 1;
    letter-spacing: 1.5px;
    align-self: center;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  /* Numbers emphasized for scanners; plain text for readers. */
  .spec .fact {
    grid-column: 1 / -1;
    grid-row: 2;
    margin: 0;
    font-size: 12px;
    line-height: 16px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .spec .fact b {
    font-weight: 650;
    color: var(--text);
  }

  .spec .fact .num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  /* Raised above the card overlay so they stay independently clickable. */
  .spec .vt,
  .spec .benign {
    grid-column: 3;
    grid-row: 1;
    position: relative;
    z-index: 1;
    justify-self: end;
    align-self: center;
    display: inline-flex;
    align-items: center;
    height: 24px;
    padding: 0 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  /* Quiet text link: amber stays reserved for data. */
  .spec .vt {
    color: var(--text-muted);
    padding: 0 4px;
    font-weight: 500;
    text-decoration: none;
  }

  /* 44px tap row without changing the visual size; extends into the card's own padding. */
  .spec .vt::after {
    content: '';
    position: absolute;
    inset: -8px -4px -12px;
  }

  .spec .vt:hover {
    color: var(--text);
    text-decoration: underline;
  }

  .spec .vt:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .spec .benign {
    color: var(--text-dim);
    border: 1px solid var(--border-strong);
  }

  .specimens > .empty {
    grid-column: 1 / -1;
  }

  .empty {
    padding: var(--space-4, 16px);
    text-align: center;
    color: var(--text-muted);
    font-size: 12.5px;
  }

  .right-col {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .relay-card {
    flex: 1 1 auto;
    min-height: 0;
  }

  .relay-rank {
    flex: 1 1 auto;
    min-height: 0;
  }

  .relay-insight {
    flex: none;
    margin-top: auto;
    padding-top: 12px;
    font-size: 12px;
  }

  /* Stacked layout: the card hugs its rows, so auto resolves to 0 and the note touched the last row. */
  @media (max-width: 900px) {
    .relay-insight {
      margin-top: 16px;
    }
  }

  .mono {
    font-family: var(--font-mono);
    font-size: 12.5px;
  }

  .num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 12.5px;
  }

  /* Mobile only: the single column buries Relay attempts last. */
  .show-all {
    display: none;
    grid-column: 1 / -1;
  }

  .show-all button {
    width: 100%;
    min-height: 44px;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--text);
    font-size: 13px;
  }

  .relay-jump {
    display: none;
    flex: none;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    box-sizing: border-box;
    min-height: 58px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    box-shadow: var(--shadow-sm);
    color: var(--text);
    text-decoration: none;
    font-size: 13px;
    font-weight: 650;
  }

  .relay-jump-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .relay-jump small {
    font-size: 12px;
    font-weight: 400;
    color: var(--text-dim);
  }

  .relay-jump:hover {
    border-color: var(--accent-dim);
  }

  .relay-jump:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .relay-jump-icon {
    flex: none;
    width: 18px;
    height: 18px;
    color: var(--accent);
    transform: rotate(90deg);
  }

  @media (max-width: 900px) {
    .relay-jump {
      display: flex;
    }

    /* grid-auto-flow must be reset; on its own, grid-template-columns cannot
       stop column flow, squeezing tiles into one unreadable row. */
    .stat-row {
      grid-auto-flow: row;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .grid-main {
      display: flex;
      flex-direction: column;
    }

    .specimens {
      grid-template-columns: 1fr;
      overflow: visible;
    }

    .show-all {
      display: block;
    }

    .specimens:not(.expanded) .spec:nth-child(n + 9):not(.picked) {
      display: none;
    }

    /* The header now wraps onto two lines, so a max-height alone left only a
       row or two of the list visible; give it a floor as well. */
    .relay-card {
      min-height: 420px;
      max-height: none;
    }
  }
</style>
