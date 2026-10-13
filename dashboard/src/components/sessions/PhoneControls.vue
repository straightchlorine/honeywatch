<script setup lang="ts">
  /**
   * Phone filter row: three pills (outcome, sort, country) that each open one bottom sheet.
   * Outcome keeps the OutcomeFilter has= semantics; sort and country are single-select.
   *
   * TODO(next PR): 470 lines - split the bottom sheet (scroll lock, Tab trap, Escape, opener
   * focus) out of the pills, and share the outcome label logic with OutcomeFilter.vue.
   */
  import { computed, nextTick, onBeforeUnmount, ref, useId, useTemplateRef, watch } from 'vue'
  import type { OutcomeCountsResponse } from '@/api/generated/types.gen'
  import { ICONS, OUTCOME_ICONS } from '@/components/icons'
  import { fmtNumber } from '@/utils/format'
  import { ALL_ROWS, MAIN_ROWS, NONE_ROW, toggleHas } from '@/utils/outcomeFilter'

  interface Opt {
    value: string
    label: string
    /** Pill text when the full label would clip in a third of the screen. */
    short?: string
    hint?: string
    icon?: string
  }

  const props = defineProps<{
    has: string
    sort: string
    country: string
    sortOptions: Opt[]
    countryOptions: Opt[]
    counts: OutcomeCountsResponse | null
  }>()
  const emit = defineEmits<{
    'update:has': [value: string]
    'update:sort': [value: string]
    'update:country': [value: string]
  }>()

  type Key = 'outcome' | 'sort' | 'country'
  const TITLES: Record<Key, string> = {
    outcome: 'Outcome',
    sort: 'Sort sessions',
    country: 'Country',
  }

  const titleId = useId()
  const openKey = ref<Key | null>(null)
  const sheet = useTemplateRef<HTMLElement>('sheet')
  const doneBtn = useTemplateRef<HTMLButtonElement>('doneBtn')
  const triggers = new Map<Key, HTMLElement>()
  const setTrigger = (k: Key) => (el: unknown) => {
    if (el instanceof HTMLElement) triggers.set(k, el)
  }

  // Three pills share the phone width, so a single selected outcome shows a one-word name.
  const OUTCOME_SHORT: Record<string, string> = {
    success: 'Control',
    commands: 'Commands',
    tcpip: 'Relay',
    downloads: 'File',
    none: 'Nothing',
  }

  const hasTokens = computed(() => (props.has ? props.has.split(',') : []))
  const sortOpt = computed(() => props.sortOptions.find((o) => o.value === props.sort))
  const countryOpt = computed(() => props.countryOptions.find((o) => o.value === props.country))

  const pills = computed(() => {
    const t = hasTokens.value
    const outcome =
      t.length === 0
        ? 'Outcome'
        : t.length === 1
          ? (ALL_ROWS.find((r) => r.token === t[0])?.label ?? 'Outcome')
          : `${t.length} outcomes`
    const outcomeText =
      t.length > 1
        ? `${t.length} types`
        : t.length === 1
          ? (OUTCOME_SHORT[t[0]!] ?? outcome)
          : outcome
    const sort = sortOpt.value?.short ?? sortOpt.value?.label ?? ''
    const country = props.country ? (countryOpt.value?.label ?? props.country) : 'Country'
    const countryText = props.country
      ? [countryOpt.value?.icon, props.country].filter(Boolean).join(' ')
      : 'Country'
    return [
      {
        key: 'outcome' as const,
        text: outcomeText,
        name: `Outcome: ${outcome}`,
        set: t.length > 0,
      },
      {
        key: 'sort' as const,
        text: sort,
        name: `Sort: ${sortOpt.value?.label ?? ''}`,
        set: props.sort !== props.sortOptions[0]?.value,
      },
      {
        key: 'country' as const,
        text: countryText,
        name: `Country: ${props.country ? country : 'all'}`,
        set: props.country !== '',
      },
    ]
  })

  const options = computed(() =>
    openKey.value === 'sort' ? props.sortOptions : props.countryOptions,
  )
  const current = computed(() => (openKey.value === 'sort' ? props.sort : props.country))

  async function openSheet(k: Key): Promise<void> {
    openKey.value = k
    await nextTick()
    const el = sheet.value
    const first =
      el?.querySelector<HTMLElement>('[aria-checked="true"]') ??
      el?.querySelector<HTMLElement>('button')
    first?.focus({ preventScroll: true })
    first?.scrollIntoView?.({ block: 'nearest' })
  }

  const root = document.documentElement
  watch(openKey, (k) => {
    root.style.overflow = k ? 'hidden' : ''
  })
  onBeforeUnmount(() => {
    root.style.overflow = ''
  })

  function close(): void {
    const k = openKey.value
    openKey.value = null
    // Safari does not focus a button on tap, so the opener is tracked, not read from activeElement.
    if (k) void nextTick(() => triggers.get(k)?.focus({ preventScroll: true }))
  }

  // Clear disables itself once nothing is set; focus moves first so Escape and the Tab trap still work.
  function clearHas(): void {
    doneBtn.value?.focus({ preventScroll: true })
    emit('update:has', '')
  }

  function pick(value: string): void {
    if (openKey.value === 'sort') emit('update:sort', value)
    else emit('update:country', value)
    close()
  }

  const FOCUSABLE = 'button:not([disabled])'
  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
      return
    }
    if (e.key !== 'Tab') return
    const items = Array.from(sheet.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
    const first = items[0]
    const last = items[items.length - 1]
    if (!first || !last) return
    const active = document.activeElement
    const inside = sheet.value?.contains(active) ?? false
    if (e.shiftKey ? !inside || active === first : !inside || active === last) {
      e.preventDefault()
      ;(e.shiftKey ? last : first).focus()
    }
  }
</script>

<template>
  <div class="pc-row">
    <button
      v-for="p in pills"
      :key="p.key"
      :ref="setTrigger(p.key)"
      type="button"
      class="pc-pill"
      :class="{ set: p.set }"
      aria-haspopup="dialog"
      :aria-expanded="openKey === p.key"
      :aria-label="p.name"
      :title="p.name"
      @click="openSheet(p.key)"
    >
      <span class="pc-text">{{ p.text }}</span>
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          d="M6 9l6 6 6-6"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>

  <Teleport to="body">
    <Transition name="pc">
      <div v-if="openKey" class="pc-root">
        <div class="pc-scrim" aria-hidden="true" @click="close"></div>
        <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- delegated Escape and Tab trap for the dialog subtree -->
        <div
          ref="sheet"
          class="pc-sheet"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          @keydown="onKeydown"
        >
          <h3 :id="titleId">{{ TITLES[openKey] }}</h3>
          <div v-if="openKey === 'outcome'" role="group" :aria-labelledby="titleId" class="pc-list">
            <template v-for="r in [...MAIN_ROWS, NONE_ROW]" :key="r.token">
              <div v-if="r.token === 'none'" class="pc-divider" aria-hidden="true"></div>
              <button
                type="button"
                role="checkbox"
                class="pc-opt"
                :aria-checked="hasTokens.includes(r.token)"
                @click="emit('update:has', toggleHas(has, r.token))"
              >
                <svg
                  class="pc-oi"
                  :style="{ color: OUTCOME_ICONS[r.token]?.color }"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                  focusable="false"
                >
                  <path :d="ICONS[OUTCOME_ICONS[r.token]!.icon]" />
                </svg>
                <span class="pc-tx">{{ r.label }}</span>
                <span class="pc-count" :class="{ bad: r.token === 'none' }">{{
                  fmtNumber(counts?.[r.countKey])
                }}</span>
                <svg class="pc-ck" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path :d="ICONS.check" />
                </svg>
              </button>
            </template>
            <div class="pc-actions">
              <button type="button" class="pc-clear" :disabled="!has" @click="clearHas">
                Clear
              </button>
              <button ref="doneBtn" type="button" class="pc-done" @click="close">Done</button>
            </div>
          </div>
          <div v-else role="radiogroup" :aria-labelledby="titleId" class="pc-list">
            <button
              v-for="o in options"
              :key="o.value"
              type="button"
              role="radio"
              class="pc-opt"
              :aria-checked="o.value === current"
              @click="pick(o.value)"
            >
              <span v-if="o.icon" class="pc-flag" aria-hidden="true">{{ o.icon }}</span>
              <span class="pc-tx">
                {{ o.label }}
                <small v-if="o.hint">{{ o.hint }}</small>
              </span>
              <svg class="pc-ck" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path :d="ICONS.check" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
  .pc-row {
    display: grid;
    /* Equal thirds, but a track grows to its pill's text when a wider system font needs it
       (font-sans is the system stack, so label widths differ per platform). The labels are short
       and fixed (one-word outcome, short sort name, flag + code), so the minimums stay small. */
    grid-template-columns: repeat(3, minmax(max-content, 1fr));
    gap: 8px;
  }
  .pc-pill {
    appearance: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 2px;
    min-width: 0;
    min-height: var(--control-h);
    box-sizing: border-box;
    padding: 6px 8px 6px 12px;
    background: transparent;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    color: var(--text-muted);
    font: 550 12.5px var(--font-sans);
    cursor: pointer;
    transition: all var(--motion-fast);
  }
  .pc-pill.set {
    color: var(--accent);
    border-color: var(--accent-dim);
    background: var(--accent-wash);
  }
  .pc-pill:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .pc-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pc-pill svg {
    flex: none;
    width: 12px;
    height: 12px;
    color: var(--text-dim);
  }
  .pc-pill[aria-expanded='true'] svg {
    transform: rotate(180deg);
  }

  .pc-root {
    position: fixed;
    inset: 0;
    z-index: 60;
  }
  .pc-scrim {
    position: absolute;
    inset: 0;
    background: rgba(10, 7, 4, 0.62);
    touch-action: none;
  }
  .pc-sheet {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    box-sizing: border-box;
    max-width: 560px;
    max-height: 78dvh;
    margin: 0 auto;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 8px 8px calc(12px + env(safe-area-inset-bottom));
    background: var(--bg-2);
    border-top: 1px solid var(--border-strong);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
  .pc-sheet h3 {
    margin: 8px 12px 6px;
    font: 700 11px var(--font-sans);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
  }
  .pc-list {
    display: flex;
    flex-direction: column;
  }
  .pc-opt {
    appearance: none;
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 48px;
    padding: 0 12px;
    background: transparent;
    border: 0;
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font: 550 14px var(--font-sans);
    text-align: left;
    cursor: pointer;
  }
  .pc-opt:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .pc-opt[aria-checked='true'] {
    color: var(--accent);
    background: var(--accent-wash);
  }
  .pc-tx {
    flex: 1;
    min-width: 0;
  }
  .pc-tx small {
    display: block;
    font: 400 12px var(--font-sans);
    color: var(--text-dim);
  }
  .pc-tx small::first-letter {
    text-transform: uppercase;
  }
  .pc-count {
    font: 11.5px var(--font-mono);
    font-variant-numeric: tabular-nums;
    color: var(--text-dim);
  }
  .pc-count.bad {
    color: var(--bad);
  }
  .pc-oi {
    flex: none;
    width: 20px;
    height: 20px;
    fill: currentColor;
  }
  .pc-ck {
    flex: none;
    width: 18px;
    height: 18px;
    fill: currentColor;
    opacity: 0;
  }
  .pc-opt[aria-checked='true'] .pc-ck {
    opacity: 1;
  }
  .pc-divider {
    border-top: 1px solid var(--border);
    margin: 4px 12px;
  }
  .pc-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
  }
  .pc-clear,
  .pc-done {
    appearance: none;
    min-height: var(--control-h);
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    font: 550 13px var(--font-sans);
    cursor: pointer;
  }
  .pc-done {
    color: var(--accent);
    border-color: var(--accent-dim);
    background: var(--accent-wash);
  }
  .pc-clear:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .pc-clear:focus-visible,
  .pc-done:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .pc-enter-active,
  .pc-leave-active {
    transition: opacity var(--motion-slow);
  }
  .pc-enter-active .pc-sheet,
  .pc-leave-active .pc-sheet {
    transition: transform var(--motion-slow) cubic-bezier(0.22, 1, 0.36, 1);
  }
  .pc-enter-from,
  .pc-leave-to {
    opacity: 0;
  }
  .pc-enter-from .pc-sheet,
  .pc-leave-to .pc-sheet {
    transform: translateY(105%);
  }
</style>
