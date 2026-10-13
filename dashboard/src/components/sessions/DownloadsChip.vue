<script setup lang="ts">
  // The session's downloads chip. One kept file links straight to its specimen on /payloads;
  // several (or an uncaptured one) open a short list. Only short digests are shown, never URLs.
  import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
  import type { DownloadResponse } from '@/api/generated/types.gen'
  import { ICONS } from '@/components/icons'
  import { benignContent, vtUrl } from '@/utils/knownDigests'
  import StoryChip from './StoryChip.vue'

  const { downloads, label, title } = defineProps<{
    downloads: readonly DownloadResponse[]
    label: string
    title: string
  }>()

  const kept = computed(() => {
    const counts = new Map<string, number>()
    for (const d of downloads) if (d.sha256) counts.set(d.sha256, (counts.get(d.sha256) ?? 0) + 1)
    return [...counts].map(([sha, n]) => ({ sha, n, benign: benignContent(sha) }))
  })
  const notKept = computed(() => downloads.filter((d) => !d.sha256).length)
  const direct = computed(() => (kept.value.length === 1 && !notKept.value ? kept.value[0]! : null))
  const to = (sha: string) => ({ name: 'payloads', hash: `#spec-${sha}` })

  const open = ref(false)
  const root = ref<HTMLElement | null>(null)
  const trigger = ref<HTMLButtonElement | null>(null)
  const list = ref<HTMLElement | null>(null)
  const pos = ref({ left: 0, top: 0, caret: 24, flip: false })
  const GAP = 6
  const EDGE = 8

  // Fixed, anchored under the chip (above when there is no room), clamped inside the viewport.
  // Rects are viewport px; the 4K shell zoom scales fixed offsets, so divide it back out.
  function place(): void {
    const t = trigger.value
    const l = list.value
    if (!t || !l) return
    const z = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--ui-zoom')) || 1
    const r = t.getBoundingClientRect()
    const w = l.offsetWidth * z
    const h = l.offsetHeight * z
    const vw = document.documentElement.clientWidth
    const vh = window.innerHeight
    // Right-aligned to the chip (it sits at the end of the tags), clamped inside the viewport.
    const x = Math.max(EDGE, Math.min(r.right - w, vw - w - EDGE))
    const below = r.bottom + GAP
    const flip = below + h > vh - EDGE && r.top - GAP - h >= EDGE
    const y = flip ? r.top - GAP - h : below
    const c = Math.max(12, Math.min(r.left + r.width / 2 - x, w - 12))
    pos.value = { left: x / z, top: y / z, caret: c / z, flip }
  }

  function close(focusTrigger = false): void {
    open.value = false
    if (focusTrigger) void nextTick(() => trigger.value?.focus())
  }
  // Touch Safari does not focus buttons, so focusout alone would leave the list stuck open.
  function onOutside(e: PointerEvent): void {
    if (!root.value?.contains(e.target as Node)) close()
  }
  function toggle(): void {
    open.value = !open.value
  }
  watch(open, (v) => {
    if (v) {
      document.addEventListener('pointerdown', onOutside, true)
      window.addEventListener('resize', place)
      window.addEventListener('scroll', place, true)
      void nextTick(place)
    } else {
      document.removeEventListener('pointerdown', onOutside, true)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  })
  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onOutside, true)
    window.removeEventListener('resize', place)
    window.removeEventListener('scroll', place, true)
  })
  function onFocusout(e: FocusEvent): void {
    if (!root.value?.contains(e.relatedTarget as Node | null)) open.value = false
  }
</script>

<template>
  <RouterLink
    v-if="direct"
    :to="to(direct.sha)"
    class="dl-chip"
    :title="`${title} - open in Payloads`"
    :aria-label="`${title}, open in Payloads`"
  >
    <StoryChip icon="file">{{ label }}</StoryChip>
  </RouterLink>
  <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- focusout/Escape bubble from the real controls inside -->
  <span v-else ref="root" class="dl-wrap" @focusout="onFocusout" @keydown.esc.stop="close(true)">
    <button
      ref="trigger"
      type="button"
      class="dl-chip"
      aria-haspopup="true"
      :aria-expanded="open"
      :title="open ? undefined : title"
      :aria-label="`${title}, show files`"
      @click="toggle"
    >
      <StoryChip icon="file">
        {{ label }}
        <template #end>
          <svg class="caret" :class="{ up: open }" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </template>
      </StoryChip>
    </button>
    <ul
      v-if="open"
      ref="list"
      class="dl-list"
      aria-label="Files from this session"
      :class="{ flip: pos.flip }"
      :style="{ left: `${pos.left}px`, top: `${pos.top}px`, '--caret': `${pos.caret}px` }"
    >
      <li v-for="k in kept" :key="k.sha" class="dl-row">
        <RouterLink
          :to="to(k.sha)"
          class="dl-item"
          :aria-label="`Open file ${k.sha.slice(0, 12)} in Payloads`"
          @click="close()"
        >
          <StoryChip icon="file"
            ><span class="dl-sha">{{ k.sha.slice(0, 12) }}</span></StoryChip
          >
          <span v-if="k.n > 1" class="dl-n">&times;{{ k.n }}</span>
        </RouterLink>
        <span v-if="k.benign" class="dl-side dl-benign">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="ICONS.check" /></svg>
          not malware
        </span>
        <a
          v-else
          class="dl-side dl-vt"
          :href="vtUrl(k.sha)"
          target="_blank"
          rel="noopener noreferrer"
          title="Open VirusTotal in a new tab"
          :aria-label="`VT: open ${k.sha.slice(0, 8)} on VirusTotal (new tab)`"
        >
          <span class="vt-pill"
            >VT
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M7 17 17 7M9 7h8v8" /></svg
          ></span>
        </a>
      </li>
      <li v-if="notKept" class="dl-row dl-none">
        <StoryChip tone="dim" icon="file">not kept</StoryChip>
        <span v-if="notKept > 1" class="dl-n">&times;{{ notKept }}</span>
      </li>
    </ul>
  </span>
</template>

<style scoped>
  .dl-wrap {
    display: inline-flex;
  }
  .dl-chip {
    display: inline-flex;
    padding: 0;
    border: 0;
    border-radius: 999px;
    background: none;
    font: inherit;
    cursor: pointer;
  }
  .dl-chip:hover {
    text-decoration: none;
  }
  .dl-chip:focus-visible {
    outline: 2px solid var(--accent-hot);
    outline-offset: 2px;
  }
  .caret {
    width: 9px;
    height: 9px;
    margin-left: -1px;
    fill: none;
    stroke: currentColor;
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: transform var(--motion-fast);
  }
  .caret.up {
    transform: rotate(180deg);
  }
  .dl-chip {
    position: relative;
  }
  @media (pointer: coarse) {
    .dl-chip::after {
      content: '';
      position: absolute;
      inset: -12px -6px;
    }
  }
  .dl-list {
    position: fixed;
    zoom: var(--ui-zoom, 1);
    z-index: 60;
    width: max-content;
    max-width: calc(100vw - 16px);
    margin: 0;
    padding: var(--space-1);
    list-style: none;
    background: var(--bg-1);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-lift);
  }
  /* Notch pointing at the chip, so the list reads as its extension. */
  .dl-list::before {
    content: '';
    position: absolute;
    top: -5px;
    left: calc(var(--caret) - 4px);
    width: 8px;
    height: 8px;
    background: var(--bg-1);
    border: solid var(--border-strong);
    border-width: 1px 0 0 1px;
    transform: rotate(45deg);
  }
  .dl-list.flip::before {
    top: auto;
    bottom: -5px;
    border-width: 0 1px 1px 0;
  }
  .dl-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    border-radius: var(--radius-sm);
  }
  .dl-item {
    flex: 1 1 auto;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-height: var(--control-h);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: var(--type-xs);
  }
  .dl-item:hover :deep(.chip::before),
  .dl-item:focus-visible :deep(.chip::before) {
    background: color-mix(in srgb, var(--accent) 30%, var(--bg-1));
  }
  .dl-item:hover {
    background: var(--surface-hover);
    color: var(--text);
    text-decoration: none;
  }
  .dl-item:focus-visible,
  .dl-vt:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .dl-sha {
    font-weight: 600;
  }
  .dl-n {
    color: var(--text-dim);
    font: 600 11.5px var(--font-mono);
  }
  .dl-side {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    min-height: var(--control-h);
    padding: 0 var(--space-1);
    font: 650 10.5px var(--font-mono);
  }
  .dl-vt {
    border-radius: var(--radius-sm);
    color: var(--accent-hot);
  }
  .vt-pill {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    height: 22px;
    padding: 0 8px;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    transition: background var(--motion-fast);
  }
  .vt-pill svg {
    width: 9px;
    height: 9px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.4;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .dl-vt:hover {
    text-decoration: none;
  }
  .dl-vt:hover .vt-pill {
    background: var(--surface-hover);
    border-color: var(--accent-dim);
  }
  .dl-benign {
    color: var(--text-dim);
    font-weight: 500;
  }
  .dl-benign svg {
    width: 10px;
    height: 10px;
    fill: currentColor;
  }
  .dl-none {
    min-height: var(--control-h);
    padding: var(--space-1) var(--space-2);
    color: var(--text-dim);
  }
  @media (pointer: coarse) {
    .dl-item,
    .dl-side,
    .dl-none {
      min-height: 44px;
    }
    .dl-vt {
      min-width: 44px;
    }
  }
</style>
