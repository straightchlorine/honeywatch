<script setup lang="ts">
  /**
   * Multi-select outcome filter for Sessions. modelValue is the API's has= value:
   * '' (none checked), 'commands,success' (AND-ed list), or 'none' (mutually
   * exclusive; server 422s on mixed has=none). NOT built on Dropdown.vue because
   * this needs per-row counts, native checkboxes, and mutual-exclusion rules
   * that single-select listbox models don't support.
   */
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
  import type { OutcomeCountsResponse } from '@/api/generated/types.gen'
  import { fmtNumber } from '@/utils/format'

  const props = defineProps<{
    modelValue: string
    counts: OutcomeCountsResponse | null
  }>()
  const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

  interface Row {
    /** has= token this row toggles. */
    token: string
    label: string
    /** Field on OutcomeCountsResponse this row's count comes from - differs
     * from `token` for "Got control": the query token is `success`
     * (auth_success), the count field is `shell` (accepted login). */
    countKey: keyof OutcomeCountsResponse
  }

  const MAIN_ROWS: Row[] = [
    { token: 'success', label: 'Got control', countKey: 'shell' },
    { token: 'commands', label: 'Ran commands', countKey: 'commands' },
    { token: 'tcpip', label: 'Tried to relay', countKey: 'tcpip' },
    { token: 'downloads', label: 'Dropped a file', countKey: 'downloads' },
  ]
  // Complement of the four above (interest == 0), not a fifth member of the
  // same set - kept out of MAIN_ROWS and given its own divider in the panel.
  const NONE_ROW: Row = { token: 'none', label: 'Nothing at all', countKey: 'none' }
  const ALL_ROWS = [...MAIN_ROWS, NONE_ROW]

  const open = ref(false)
  const root = ref<HTMLElement | null>(null)
  const panelId = 'outcome-filter-panel'
  const headingId = 'outcome-filter-heading'

  const selected = computed(() => new Set(props.modelValue ? props.modelValue.split(',') : []))
  const selectedCount = computed(() => selected.value.size)

  const triggerLabel = computed(() => {
    if (selectedCount.value === 0) return 'Outcome'
    if (selectedCount.value === 1) {
      const [token] = selected.value
      const row = ALL_ROWS.find((r) => r.token === token)
      return `Outcome: ${row?.label ?? ''}`
    }
    return `Outcome: ${selectedCount.value} selected`
  })

  function isChecked(token: string): boolean {
    return selected.value.has(token)
  }

  function countText(row: Row): string {
    return fmtNumber(props.counts?.[row.countKey])
  }

  function toggleToken(token: string): void {
    const next = new Set(selected.value)
    if (token === 'none') {
      // Ticking "none" clears every other bucket - has=none plus anything
      // else is always the empty set server-side.
      if (next.has('none')) next.delete('none')
      else {
        next.clear()
        next.add('none')
      }
    } else {
      if (next.has(token)) next.delete(token)
      else {
        next.delete('none')
        next.add(token)
      }
    }
    // Canonical row order, not insertion order, so the emitted string is
    // deterministic regardless of click order.
    emit(
      'update:modelValue',
      ALL_ROWS.filter((r) => next.has(r.token))
        .map((r) => r.token)
        .join(','),
    )
  }

  function clearAll(): void {
    emit('update:modelValue', '')
  }

  async function openPanel(): Promise<void> {
    open.value = true
    await nextTick()
    root.value?.querySelector<HTMLInputElement>('.of-panel input[type="checkbox"]')?.focus()
  }

  function close(focusTrigger = true): void {
    open.value = false
    if (focusTrigger) {
      void nextTick(() => (root.value?.querySelector('.of-trigger') as HTMLElement | null)?.focus())
    }
  }

  function onTriggerClick(): void {
    if (open.value) close()
    else void openPanel()
  }

  function onPanelKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }

  // Closing cannot be decided by focus alone: a real click on the (unfocusable)
  // <label> text holds the button ~100ms, during which a deferred focus-check
  // could run mid-press, close the panel (v-if), and destroy the label before
  // the checkbox's default click reaches it. So the two ways out are handled
  // separately and never depend on timing: focusout with relatedTarget outside
  // closes (Tab out); clicking away closes (document pointerdown in capture phase).
  function onFocusout(e: FocusEvent): void {
    const next = e.relatedTarget as Node | null
    // Pressing non-focusable text sends focus to nearest focusable ancestor
    // (browser fallback), not null - a distinct case from deliberate Tab out.
    if (!next) return
    if (root.value?.contains(next)) return
    if (next.contains(root.value)) return
    open.value = false
  }

  function onDocumentPointerDown(e: PointerEvent): void {
    if (open.value && !root.value?.contains(e.target as Node)) open.value = false
  }

  // Capture phase: fires even if a child stops propagation.
  onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown, true))
  onUnmounted(() => document.removeEventListener('pointerdown', onDocumentPointerDown, true))
</script>

<template>
  <div ref="root" class="outcome-filter" @focusout="onFocusout">
    <span class="of-trigger-wrap">
      <button
        type="button"
        class="of-trigger"
        aria-haspopup="true"
        :aria-expanded="open"
        :aria-controls="open ? panelId : undefined"
        @click="onTriggerClick"
      >
        <span class="of-trigger-label">{{ triggerLabel }}</span>
        <svg class="chevron" :class="{ 'chevron-open': open }" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <button
        v-if="selectedCount > 0"
        type="button"
        class="of-clear"
        aria-label="Clear outcome filter"
        @click="clearAll"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
        </svg>
      </button>
    </span>

    <!-- @keydown here only catches Escape bubbling up from whichever checkbox
         has focus (role="group" is correctly non-interactive on its own) -
         same justified bypass Dropdown.vue takes for its listbox. -->
    <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -->
    <div
      v-if="open"
      :id="panelId"
      class="of-panel"
      role="group"
      :aria-labelledby="headingId"
      @keydown="onPanelKeydown"
    >
      <div :id="headingId" class="of-heading">Outcome</div>
      <label v-for="row in MAIN_ROWS" :key="row.token" class="of-row" :for="`of-cb-${row.token}`">
        <input
          :id="`of-cb-${row.token}`"
          type="checkbox"
          :checked="isChecked(row.token)"
          @change="toggleToken(row.token)"
        />
        <span class="of-row-label">{{ row.label }}</span>
        <span class="of-row-count">{{ countText(row) }}</span>
      </label>
      <div class="of-divider" aria-hidden="true"></div>
      <label class="of-row" :for="`of-cb-${NONE_ROW.token}`">
        <input
          :id="`of-cb-${NONE_ROW.token}`"
          type="checkbox"
          :checked="isChecked(NONE_ROW.token)"
          @change="toggleToken(NONE_ROW.token)"
        />
        <span class="of-row-label">{{ NONE_ROW.label }}</span>
        <span class="of-row-count of-count-bad">{{ countText(NONE_ROW) }}</span>
      </label>
    </div>
  </div>
</template>

<style scoped>
  .outcome-filter {
    position: relative;
    display: inline-flex;
  }

  .of-trigger-wrap {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .of-trigger {
    appearance: none;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-height: var(--control-h);
    box-sizing: border-box;
    background: transparent;
    border: 1px solid var(--border-strong);
    border-radius: 999px;
    color: var(--text-muted);
    font: 550 12.5px var(--font-sans);
    padding: 6px 14px;
    cursor: pointer;
    transition: all var(--motion-fast);
  }

  .of-trigger:hover {
    color: var(--text);
    border-color: var(--accent-dim);
  }

  .of-trigger:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .of-trigger[aria-expanded='true'],
  .outcome-filter:has(.of-clear) .of-trigger {
    border-color: var(--accent);
    color: var(--text);
  }

  .of-trigger-label {
    white-space: nowrap;
  }

  .chevron {
    flex: 0 0 auto;
    width: 12px;
    height: 12px;
    transition: transform var(--motion-fast) ease;
  }

  .chevron-open {
    transform: rotate(180deg);
  }

  .of-clear {
    appearance: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 999px;
    color: var(--text-dim);
    cursor: pointer;
    transition: all var(--motion-fast);
  }

  .of-clear:hover {
    color: var(--text);
    background: var(--surface-hover);
  }

  .of-clear:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .of-clear svg {
    width: 12px;
    height: 12px;
  }

  .of-panel {
    position: absolute;
    z-index: 20;
    top: calc(100% + 6px);
    left: 0;
    width: 300px;
    box-sizing: border-box;
    background: var(--bg-1);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    padding: var(--space-1);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .of-heading {
    font-size: 10.5px;
    font-weight: 650;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding: 6px 8px 4px;
  }

  .of-row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 8px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    color: var(--text-muted);
    cursor: pointer;
  }

  .of-row:hover {
    background: var(--surface-hover);
    color: var(--text);
  }

  .of-row:has(input:focus-visible) {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  /* Custom styling: accent-color paints only checked state; unchecked fell
     back to browser default (light white-grey on dark panel). */
  .of-row input[type='checkbox'] {
    appearance: none;
    -webkit-appearance: none;
    flex: 0 0 auto;
    width: 15px;
    height: 15px;
    margin: 0;
    box-sizing: border-box;
    display: inline-grid;
    place-content: center;
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    background: var(--bg-0);
    cursor: pointer;
    transition:
      background-color 120ms ease,
      border-color 120ms ease;
  }

  .of-row:hover input[type='checkbox'] {
    border-color: var(--accent-dim);
  }

  .of-row input[type='checkbox']:checked {
    background: var(--accent);
    border-color: var(--accent);
  }

  /* CSS-drawn tick rather than a glyph or an image: keeps the source ASCII and
     the mark inherits the panel's own colours. */
  .of-row input[type='checkbox']::after {
    content: '';
    width: 8px;
    height: 4px;
    border-left: 2px solid var(--bg-0);
    border-bottom: 2px solid var(--bg-0);
    border-radius: 1px;
    transform: translateY(-1px) rotate(-45deg);
    opacity: 0;
  }

  .of-row input[type='checkbox']:checked::after {
    opacity: 1;
  }

  .of-row-label {
    flex: 1 1 auto;
  }

  .of-row-count {
    flex: 0 0 auto;
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-variant-numeric: tabular-nums;
    color: var(--text-dim);
  }

  .of-count-bad {
    color: var(--bad);
  }

  .of-divider {
    border-top: 1px solid var(--border);
    margin: 2px 4px;
  }
</style>
