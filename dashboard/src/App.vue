<script setup lang="ts">
import { ref, onMounted } from "vue";
import IconLink from "./components/IconLink.vue";
import BarChart from "./components/BarChart.vue";
import ActivityChart from "./components/ActivityChart.vue";
import HeatmapGrid from "./components/HeatmapGrid.vue";

interface StatsSnapshot {
  total_sessions: number;
  unique_ips: number;
  total_auth_attempts: number;
}

interface BarItem {
  label: string;
  count: number;
}

interface TrendData {
  current: number;
  previous: number;
  delta: number;
  pct_change: number | null;
}

interface HeatmapPoint {
  hour: number;
  weekday: number;
  count: number;
}

const stats = ref<StatsSnapshot | null>(null);
const topPasswords = ref<BarItem[]>([]);
const topCountries = ref<BarItem[]>([]);
const trend = ref<TrendData | null>(null);
const heatmap = ref<HeatmapPoint[]>([]);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const [sR, pwR, coR, trR, hmR] = await Promise.all([
      fetch("/api/stats/totals"),
      fetch("/api/stats/top-passwords"),
      fetch("/api/stats/top-countries"),
      fetch("/api/stats/trend?period_days=7"),
      fetch("/api/stats/heatmap"),
    ]);

    if (!sR.ok || !pwR.ok || !coR.ok || !trR.ok || !hmR.ok)
      throw new Error("API error");

    const [s, pw, co, tr, hm] = await Promise.all([
      sR.json(),
      pwR.json(),
      coR.json(),
      trR.json(),
      hmR.json(),
    ]);

    stats.value = s;
    topPasswords.value = pw.map((p: { password: string; count: number }) => ({
      label: p.password,
      count: p.count,
    }));
    topCountries.value = co.map(
      (c: { country: string | null; country_code: string | null; count: number }) => ({
        label: c.country ?? c.country_code ?? "Unknown",
        count: c.count,
      })
    );
    trend.value = tr;
    heatmap.value = hm;
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});

function fmtDelta(t: TrendData): string {
  const sign = t.delta >= 0 ? "+" : "";
  const pct = t.pct_change !== null ? ` (${sign}${t.pct_change}%)` : "";
  return `${sign}${t.delta}${pct}`;
}
</script>

<template>
  <main>
    <header>
      <h1>Honeywatch</h1>
      <p class="tag">SSH honeypot telemetry</p>
    </header>

    <p v-if="error" class="err">API unreachable ({{ error }})</p>

    <template v-if="stats">
      <!-- Summary cards -->
      <section class="stats">
        <div>
          <span class="n">{{ stats.total_sessions.toLocaleString() }}</span>
          <span class="l">sessions</span>
        </div>
        <div>
          <span class="n">{{ stats.unique_ips.toLocaleString() }}</span>
          <span class="l">unique IPs</span>
        </div>
        <div>
          <span class="n">{{ stats.total_auth_attempts.toLocaleString() }}</span>
          <span class="l">auth attempts</span>
        </div>
        <div v-if="trend">
          <span
            class="n"
            :class="trend.delta >= 0 ? 'up' : 'down'"
          >{{ fmtDelta(trend) }}</span>
          <span class="l">vs prev 7 days</span>
        </div>
      </section>

      <!-- Top passwords + top countries -->
      <section class="two-col">
        <BarChart title="Top Passwords" :items="topPasswords" />
        <BarChart title="Top Countries" :items="topCountries" />
      </section>

      <!-- Activity time series -->
      <ActivityChart />

      <!-- Heatmap -->
      <HeatmapGrid :data="heatmap" />
    </template>

    <p v-else-if="!error" class="muted">Loading…</p>

    <footer>
      <div class="credits">
        <p class="credits-label">
          <span>Piotr Krzysztof Lis</span>
          <span class="icons">
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/straightchlorine/"
              label="Piotr on LinkedIn"
            />
            <IconLink
              icon="github"
              href="https://github.com/straightchlorine"
              label="Piotr on GitHub"
            />
            <IconLink
              icon="codeberg"
              href="https://codeberg.org/piotrkrzysztof"
              label="Piotr on Codeberg"
            />
          </span>
        </p>
        <p class="credits-label">
          <span>Jakub Kucharski</span>
          <span class="icons">
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/jakub-kucharski-360811305/"
              label="Jakub on LinkedIn"
            />
            <IconLink
              icon="github"
              href="https://github.com/kubson2002k"
              label="Jakub on GitHub"
            />
          </span>
        </p>
      </div>

      <p class="repo">
        <IconLink
          icon="github"
          href="https://github.com/straightchlorine/honeywatch"
          label="Source on GitHub"
        />
      </p>
    </footer>
  </main>
</template>
