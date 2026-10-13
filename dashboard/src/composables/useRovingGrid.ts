import { computed, onScopeDispose, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { useHwTooltip, type TooltipRow } from '@/composables/useHwTooltip'

interface Opts<C> {
  /** Row-major; every `role="button"` in the owning svg is one cell, in this order. */
  cells: MaybeRefOrGetter<C[]>
  cols: MaybeRefOrGetter<number>
  /** Tab stop until a cell has been focused. */
  home: MaybeRefOrGetter<string | undefined>
  /** Hex the focus ring wraps. */
  geom: (c: C) => { cx: number; cy: number; r: number }
  tip: (c: C) => [string, TooltipRow[]]
  /** Enter/Space; defaults to re-showing the tooltip. */
  activate?: (c: C) => void
}

/** Old browsers reject `:focus-visible`; show the ring then, the safe default for keyboard users. */
function isFocusVisible(el: Element): boolean {
  try {
    return el.matches(':focus-visible')
  } catch {
    return true
  }
}

/** Cell index an arrow, Home or End key moves to from cell `i`; undefined for other keys. */
function stepIndex(
  key: string,
  ctrl: boolean,
  i: number,
  n: number,
  last: number,
): number | undefined {
  const row = i - (i % n)
  const rowEnd = Math.min(row + n - 1, last)
  switch (key) {
    case 'ArrowLeft':
      return Math.max(i - 1, row)
    case 'ArrowRight':
      return Math.min(i + 1, rowEnd)
    case 'ArrowUp':
      return i - n < 0 ? i : i - n
    case 'ArrowDown':
      return i + n > last ? i : i + n
    case 'Home':
      return ctrl ? 0 : row
    case 'End':
      return ctrl ? last : rowEnd
    default:
      return undefined
  }
}

/**
 * Roving tabindex (as WorldMap): the grid is one Tab stop - the cell last
 * focused, else `home` - and arrows walk the rest, clamping at the edges.
 * Focus anchors the tooltip to the cell; Escape dismisses it.
 */
export function useRovingGrid<C extends { key: string }>(o: Opts<C>) {
  const tt = useHwTooltip()
  const rovingKey = ref<string | null>(null)
  const focusedKey = ref<string | null>(null)
  const focusVisible = ref(false)
  const tabKey = computed(() =>
    toValue(o.cells).some((c) => c.key === rovingKey.value) ? rovingKey.value : toValue(o.home),
  )
  const ring = computed(() => {
    if (!focusVisible.value) return null
    const c = toValue(o.cells).find((x) => x.key === focusedKey.value)
    return c ? o.geom(c) : null
  })
  // A focused cell removed without a blur would leave the shared bubble up.
  onScopeDispose(() => {
    if (focusedKey.value !== null) tt.hide(true)
  })

  function onFocus(c: C, e: FocusEvent): void {
    const el = e.currentTarget as Element
    rovingKey.value = c.key
    focusedKey.value = c.key
    focusVisible.value = isFocusVisible(el)
    tt.showAt(el, ...o.tip(c))
  }
  function onBlur(): void {
    focusedKey.value = null
    tt.hide()
  }
  function onKeydown(c: C, e: KeyboardEvent): void {
    const el = e.currentTarget as Element
    if (e.key === 'Escape') {
      tt.hide(true)
      return
    }
    if (e.key === 'Enter' || e.key === ' ') {
      if (e.altKey || e.metaKey || e.ctrlKey) return
      e.preventDefault()
      if (o.activate) o.activate(c)
      else tt.showAt(el, ...o.tip(c))
      return
    }
    const cells = toValue(o.cells)
    const to = stepIndex(e.key, e.ctrlKey, cells.indexOf(c), toValue(o.cols), cells.length - 1)
    if (to === undefined || e.altKey || e.metaKey) return
    const next = cells[to]
    if (!next) return
    e.preventDefault()
    rovingKey.value = next.key
    el.closest('svg')?.querySelectorAll<SVGElement>('[role="button"]')[to]?.focus()
  }

  return { tabKey, ring, onFocus, onBlur, onKeydown }
}
