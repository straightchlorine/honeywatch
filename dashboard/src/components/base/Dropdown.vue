<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

interface DropdownOption {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  options: DropdownOption[]
  /** id of the visible field label, referenced by the trigger + listbox. */
  labelId: string
  /** Stable id prefix for the trigger button + option ids. */
  buttonId: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const activeIndex = ref(0)
const root = ref<HTMLElement | null>(null)
const listRef = ref<HTMLElement | null>(null)

const selectedIndex = computed(() => {
  const i = props.options.findIndex((o) => o.value === props.modelValue)
  return i >= 0 ? i : 0
})
const selectedLabel = computed(() => props.options[selectedIndex.value]?.label ?? '')
const listId = computed(() => `${props.buttonId}-list`)
const optionId = (i: number) => `${props.buttonId}-opt-${i}`

async function openList(): Promise<void> {
  open.value = true
  activeIndex.value = selectedIndex.value
  await nextTick()
  listRef.value?.focus()
}

function close(focusButton = true): void {
  open.value = false
  if (focusButton) {
    void nextTick(() => (root.value?.querySelector('.dd-button') as HTMLElement | null)?.focus())
  }
}

function choose(i: number): void {
  const opt = props.options[i]
  if (opt) emit('update:modelValue', opt.value)
  close()
}

function onButtonKeydown(e: KeyboardEvent): void {
  if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
    e.preventDefault()
    void openList()
  }
}

function onListKeydown(e: KeyboardEvent): void {
  const last = props.options.length - 1
  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      activeIndex.value = Math.min(activeIndex.value + 1, last)
      break
    case 'ArrowUp':
      e.preventDefault()
      activeIndex.value = Math.max(activeIndex.value - 1, 0)
      break
    case 'Home':
      e.preventDefault()
      activeIndex.value = 0
      break
    case 'End':
      e.preventDefault()
      activeIndex.value = last
      break
    case 'Enter':
    case ' ':
      e.preventDefault()
      choose(activeIndex.value)
      break
    case 'Escape':
      e.preventDefault()
      close()
      break
    case 'Tab':
      close(false)
      break
  }
}

// Close when focus leaves the component entirely (covers click-outside, since
// the listbox holds focus while open).
function onFocusout(e: FocusEvent): void {
  if (!root.value?.contains(e.relatedTarget as Node | null)) open.value = false
}
</script>

<template>
  <div ref="root" class="dropdown" @focusout="onFocusout">
    <button
      :id="buttonId"
      type="button"
      class="dd-button"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="open ? listId : undefined"
      :aria-labelledby="`${labelId} ${buttonId}`"
      @click="open ? close() : openList()"
      @keydown="onButtonKeydown"
    >
      <span class="dd-value">{{ selectedLabel }}</span>
      <svg
        class="chevron"
        :class="{ 'chevron-open': open }"
        viewBox="0 0 12 12"
        aria-hidden="true"
        focusable="false"
      >
        <path
          d="M2.5 4.5 6 8l3.5-3.5"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <!-- Listbox keyboard handling lives on the focused <ul> via
         aria-activedescendant (the active option is tracked there, not focused
         individually), and the per-option mouse handlers are pointer sugar -- so
         the focus / static-interaction / mouse-without-key rules don't apply. -->
    <!-- eslint-disable vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/interactive-supports-focus -->
    <ul
      v-if="open"
      :id="listId"
      ref="listRef"
      class="dd-list"
      role="listbox"
      tabindex="-1"
      :aria-labelledby="labelId"
      :aria-activedescendant="optionId(activeIndex)"
      @keydown="onListKeydown"
    >
      <li
        v-for="(opt, i) in options"
        :id="optionId(i)"
        :key="opt.value"
        class="dd-option"
        :class="{ 'dd-active': i === activeIndex, 'dd-selected': opt.value === modelValue }"
        role="option"
        :aria-selected="opt.value === modelValue"
        @mousedown.prevent
        @mousemove="activeIndex = i"
        @click="choose(i)"
      >
        {{ opt.label }}
      </li>
    </ul>
    <!-- eslint-enable vuejs-accessibility/click-events-have-key-events, vuejs-accessibility/no-static-element-interactions, vuejs-accessibility/interactive-supports-focus -->
  </div>
</template>

<style scoped>
.dropdown {
  position: relative;
  display: inline-flex;
}

.dd-button {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  /* Grow to fit the full label (e.g. entire country names) -- min-width keeps
     short values aligned, no ellipsis truncation on the trigger. */
  min-width: 160px;
  width: auto;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
  font-family: inherit;
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
  cursor: pointer;
  text-align: left;
  transition:
    background var(--motion-fast) ease,
    border-color var(--motion-fast) ease;
}

.dd-button:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.dd-button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.dd-value {
  white-space: nowrap;
}

.chevron {
  flex: 0 0 auto;
  width: 12px;
  height: 12px;
  color: var(--text-dim);
  transition: transform var(--motion-fast) ease;
}

.chevron-open {
  transform: rotate(180deg);
}

.dd-list {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  min-width: 100%;
  max-height: 280px;
  overflow-y: auto;
  margin: 0;
  padding: var(--space-1);
  list-style: none;
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
}

.dd-list:focus-visible {
  outline: none;
}

.dd-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--type-sm);
  line-height: var(--type-sm-lh);
  color: var(--text-muted);
  white-space: nowrap;
  cursor: pointer;
}

.dd-option.dd-active {
  background: var(--surface-hover);
  color: var(--text);
}

.dd-option.dd-selected {
  color: var(--accent);
  font-weight: 600;
}

.dd-option.dd-selected::before {
  content: '✓';
  font-size: var(--type-xs);
}

.dd-option:not(.dd-selected)::before {
  content: '';
  width: var(--type-xs);
}
</style>
