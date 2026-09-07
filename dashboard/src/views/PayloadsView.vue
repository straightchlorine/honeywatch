<script setup lang="ts">
  /**
   * Payloads: captured files as "specimens". Backend has no "kind" field
   * (miner/botnet/dropper), so kind filter is omitted to avoid UI controls without data.
   */
  import { computed, onMounted, onUnmounted, useTemplateRef } from 'vue'
  import { useQuery } from '@tanstack/vue-query'
  import {
    statsDownloadsOptions,
    statsTcpipDestinationsOptions,
    statsOutcomesOptions,
  } from '@/api/generated/@tanstack/vue-query.gen'
  import type { PayloadDownloadResponse, TcpipDestinationResponse } from '@/api/generated/types.gen'
  import PageShell from '@/components/layout/PageShell.vue'
  import TopBar from '@/components/layout/TopBar.vue'
  import HwCard from '@/components/base/HwCard.vue'
  import { benignContent } from '@/utils/knownDigests'
  import StatTile from '@/components/base/StatTile.vue'
  import InfoDot from '@/components/base/InfoDot.vue'
  import RankList, { type RankRow } from '@/components/base/RankList.vue'
  import InsightNote from '@/components/base/InsightNote.vue'
  import { useCountryFlag } from '@/composables/useCountryFlag'
  import { RouterLink } from 'vue-router'
  import { useHwTooltip } from '@/composables/useHwTooltip'
  import { countryDisplayName } from '@/utils/countries'
  import { fmtNumber, fmtRelativeTime } from '@/utils/format'
  import { cappedFracs } from '@/utils/cappedFracs'

  const tt = useHwTooltip()

  /**
   * Fade indicator when content is cut off by scroll height. Reuses the pattern
   * RankList already implements; two call sites don't justify extraction.
   */
  function useMoreFade(name: string) {
    const el = useTemplateRef<HTMLElement>(name)
    function check(): void {
      const n = el.value
      if (n) n.classList.toggle('has-more', n.scrollTop + n.clientHeight < n.scrollHeight - 4)
    }
    const ro = new ResizeObserver(check)
    onMounted(() => {
      check()
      if (el.value) ro.observe(el.value)
    })
    onUnmounted(() => ro.disconnect())
    return check
  }

  const checkSpecimens = useMoreFade('specimensEl')

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

  await Promise.all([downloadsQ.suspense(), tcpipQ.suspense(), outcomesQ.suspense()])


  const downloads = computed<PayloadDownloadResponse[]>(() => downloadsQ.data.value ?? [])
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

  const fetchedLabel = computed(() =>
    outcomes.value ? fmtNumber(outcomes.value.downloads) : '-',
  )
  const fetchedMeta = computed(() => {
    const o = outcomes.value
    if (!o) return ''
    const ratio = oneIn(o.downloads, o.shell)
    return ratio ? `${ratio} of the ${fmtNumber(o.shell)} that got control` : ''
  })
  const relayLabel = computed(() => (outcomes.value ? fmtNumber(outcomes.value.tcpip) : '-'))
  const relayMeta = computed(() => {
    const o = outcomes.value
    if (!o) return ''
    const ratio = oneIn(o.tcpip, o.total)
    return ratio ? `${ratio} - the honeypot blocked every one` : ''
  })

  /** Inclusive span of the shelf, not of the honeypot's uptime. */
  const windowLabel = computed(() => {
    const first = downloads.value.map((d) => d.first_seen).filter(Boolean).sort()[0]
    const last = downloads.value
      .map((d) => d.last_seen)
      .filter(Boolean)
      .sort()
      .at(-1)
    if (!first || !last) return '-'
    // Calendar days, not elapsed hours: the meta line names two DATES, so a
    // span half a day short would print "87 days" under "May 31 to Aug 27".
    const day = (iso: string) => Math.floor(new Date(iso).getTime() / 86_400_000)
    const days = day(last) - day(first)
    return days < 1 ? 'one day' : `${fmtNumber(days)} days`
  })
  const windowMeta = computed(() => {
    const first = downloads.value.map((d) => d.first_seen).filter(Boolean).sort()[0]
    const last = downloads.value
      .map((d) => d.last_seen)
      .filter(Boolean)
      .sort()
      .at(-1)
    if (!first || !last) return ''
    return `${fmtShortDate(first)} to ${fmtShortDate(last)}, newest ${fmtRelativeTime(last)}`
  })

  const shownDownloads = computed(() => downloads.value)

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
  function vtUrl(sha256: string): string {
    return `https://www.virustotal.com/gui/file/${sha256}`
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
  /** Classify by port number, not outcome label, so renaming a label can never flip the badge color. */
  const MAIL = new Set([25, 465, 587, 2525])
  function portBadgeClass(port: number): RankRow['badgeClass'] {
    if (MAIL.has(port)) return 'bad'
    if (port === 53 || port === 3478) return 'dim'
    return 'amber'
  }

  const relayRows = computed<RankRow[]>(() => {
    const { frac, over } = cappedFracs(tcpip.value.map((t) => t.sessions))
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
        over: over(t.sessions),
        badge: String(t.port),
        badgeClass: portBadgeClass(t.port),
        sub: `${portService(t.port)} . ${fmtNumber(t.hosts)} host${t.hosts === 1 ? '' : 's'} . ${where}`,
      }
    })
  })

  // Mail ports distinguish relay probes from ordinary outbound noise.
  const MAIL_PORTS = new Set([25, 465, 587])
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
          >what they leave behind - every file written to the honeypot is saved here</span
        >
      </div>

      <section class="stat-row" aria-label="Totals">
        <StatTile label="Sessions that fetched a file" :value="fetchedLabel">
          <template #label-extra>
            <InfoDot
              title="Sessions that fetched a file"
              text="Sessions that downloaded at least one file. A session that fetched two files still counts once."
            />
          </template>
          <template #meta>{{ fetchedMeta }}</template>
        </StatTile>
        <StatTile label="Files kept" :value="fmtNumber(specimenCount)">
          <template #label-extra>
            <InfoDot
              title="Files kept"
              text="Different files, each counted once. Two harmless leftovers - a blank line, and the text admin:admin - are included because attackers really wrote them."
            />
          </template>
          <template #meta>
            {{ singletonCount }} seen only once - {{ fmtNumber(captureCount) }} files in all
          </template>
        </StatTile>
        <StatTile label="Date range" :value="windowLabel">
          <template #label-extra>
            <InfoDot
              title="Date range"
              text="First file to most recent. The honeypot has been running longer - this is only the span the files cover."
            />
          </template>
          <template #meta>{{ windowMeta }}</template>
        </StatTile>
        <StatTile label="Sessions that tried to relay" :value="relayLabel">
          <template #label-extra>
            <InfoDot
              title="Sessions that tried to relay"
              text="Sessions that asked the honeypot to forward a connection elsewhere. The honeypot blocked every one. Counted once per session."
            />
          </template>
          <template #meta>{{ relayMeta }}</template>
        </StatTile>
      </section>

      <div class="grid-main">
        <HwCard
          class="spec-card"
          title="Specimens"
          :note="`${specimenCount} captured payload specimens`"
        >
          <ul
            ref="specimensEl"
            class="specimens"
            tabindex="0"
            aria-label="Captured files"
            @scroll.passive="checkSpecimens"
          >
            <li v-for="d in shownDownloads" :key="d.sha256" :class="{ recurring: d.sessions > 1 }" class="spec">
              <RouterLink class="spec-link" :to="sessionsFor(d)">
                <span class="mono head-sha" aria-hidden="true">{{ shaPrefix(d.sha256) }}</span>
                <span class="visually-hidden">{{ cardLabel(d) }}</span>
              </RouterLink>
              <span
                class="flags"
                aria-hidden="true"
                @pointerenter="tt.show(originLabel(d))"
                @pointermove="tt.move($event)"
                @pointerleave="tt.hide()"
                >{{ flagsFor(d.countries) }}</span
              >
              <span v-if="benignContent(d.sha256)" class="benign">not malware</span>
              <a v-else class="vt" :href="vtUrl(d.sha256)" target="_blank" rel="noopener noreferrer"
                >VirusTotal</a
              >
              <p class="fact">
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
            <li v-if="!shownDownloads.length" class="empty">No files captured yet.</li>
          </ul>
        </HwCard>

        <div class="right-col">
          <HwCard
            title="Relay attempts"
            :note="`top ${tcpip.length} networks attackers tried to reach`"
            class="relay-card"
          >
            <RankList
              class="relay-rank"
              :rows="relayRows"
              label-width="150px"
              badge-width="46px"
            />
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

  .tile-muted :deep(.value) {
    color: var(--text-muted);
  }

  .tile-meta-text {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
    align-content: start;
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
    grid-template-columns: auto auto 1fr auto;
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
  .spec:focus-within {
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
    font-size: 11px;
    line-height: 1;
    letter-spacing: 1.5px;
    align-self: center;
  }

  /* Numbers emphasized for scanners; plain text for readers. */
  .spec .fact {
    grid-column: 1 / -1;
    grid-row: 2;
    margin: 0;
    font-size: 11.5px;
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
    grid-column: 4;
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
    font-size: 10.5px;
    font-weight: 650;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }

  .spec .vt {
    color: var(--accent-hot);
    background: var(--accent-wash);
    border: 1px solid var(--accent-edge);
    text-decoration: none;
    transition: background var(--motion-fast);
  }

  .spec .vt:hover {
    background: var(--accent-glow);
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








  .benign {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 2px 7px;
    border-radius: 999px;
    color: var(--text-dim);
    border: 1px solid var(--border-strong);
    white-space: nowrap;
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

  @media (max-width: 900px) {
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

    .relay-card {
      max-height: 320px;
    }
  }
</style>
