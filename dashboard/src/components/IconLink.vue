<script setup lang="ts">
import { ICONS, type IconName } from "./icons";

const props = defineProps<{
  icon: IconName;
  href: string;
  label: string;
}>();
</script>

<template>
  <a
    :href="href"
    :aria-label="label"
    :title="label"
    target="_blank"
    rel="noopener noreferrer"
    class="icon-link"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path :d="ICONS[props.icon]" />
    </svg>
  </a>
</template>

<style scoped>
.icon-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  color: var(--muted);
  transition: color 120ms ease, background 120ms ease;
}

.icon-link:hover {
  color: var(--fg);
  background: #1a1f26;
}

.icon-link svg {
  width: 1.1rem;
  height: 1.1rem;
  fill: currentColor;
}
</style>
