<script setup lang="ts">
import { ref, onMounted } from "vue";
import IconLink from "./components/IconLink.vue";

const stats = ref<{ total_sessions: number; unique_ips: number } | null>(null);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const r = await fetch("/api/stats");
    if (!r.ok) throw new Error(`${r.status}`);
    stats.value = await r.json();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  }
});
</script>

<template>
  <main>
    <header>
      <h1>Honeywatch</h1>
      <p class="tag">SSH honeypot telemetry</p>
    </header>

    <section v-if="stats" class="stats">
      <div>
        <span class="n">{{ stats.total_sessions.toLocaleString() }}</span>
        <span class="l">sessions</span>
      </div>
      <div>
        <span class="n">{{ stats.unique_ips.toLocaleString() }}</span>
        <span class="l">unique IPs</span>
      </div>
    </section>
    <p v-else-if="error" class="err">API unreachable ({{ error }})</p>
    <p v-else class="muted">Loading…</p>

    <footer>
      <div class="credits">
        <p class="credits-label">
          <span>Piotr Krzysztof Lis</span>
          <span class="icons">
            <IconLink
              icon="github"
              href="https://github.com/straightchlorine"
              label="Piotr on GitHub"
            />
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/straightchlorine/"
              label="Piotr on LinkedIn"
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
              icon="github"
              href="https://github.com/kubson2002k"
              label="Jakub on GitHub"
            />
            <IconLink
              icon="linkedin"
              href="https://www.linkedin.com/in/jakub-kucharski-360811305/"
              label="Jakub on LinkedIn"
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
