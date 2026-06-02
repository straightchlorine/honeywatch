import { onScopeDispose, reactive } from 'vue'

export interface TooltipState {
  visible: boolean
  /** Cursor viewport coordinates the bubble anchors to. */
  x: number
  y: number
  text: string
}

export interface TooltipController {
  state: TooltipState
  show: (text: string, ev: MouseEvent | FocusEvent) => void
  hide: () => void
}

// Touch-primary devices fire `mouseenter` on tap but never `mouseleave`, so a
// hover bubble would stick forever. Tooltips are hover-only visual sugar (the
// data is in the visible labels / offscreen lists), so we just suppress them
// there. Guard matchMedia for SSR / jsdom (the test stub returns matches:false,
// i.e. hover-capable, so unit tests keep exercising show()).
function canHover(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true
  return !window.matchMedia('(hover: none)').matches
}

/**
 * Shared state for a single themed `<Tooltip>`. One controller drives one
 * bubble; bind it to many triggers (e.g. every heatmap cell) so a hot grid
 * renders a single overlay instead of one component per cell. The bubble tracks
 * the cursor (clientX/clientY), so it works for SVG cells and DOM rows alike.
 *
 * Tooltips here are mouse-only visual sugar -- the accessible data path is the
 * visible text plus the offscreen lists each chart already ships (mirrors the
 * world-map pattern), so there is no focus/keyboard wiring.
 *
 * Visibility is self-managing: once shown, a click/tap/scroll anywhere or Esc
 * dismisses it. Without this the bubble freezes whenever its trigger unmounts
 * (e.g. a chart re-render or a view transition) before `mouseleave` fires.
 */
export function useTooltip(): TooltipController {
  const state = reactive<TooltipState>({ visible: false, x: 0, y: 0, text: '' })

  function onKey(ev: KeyboardEvent): void {
    if (ev.key === 'Escape') hide()
  }

  function addGlobals(): void {
    document.addEventListener('pointerdown', hide, true)
    window.addEventListener('scroll', hide, { capture: true, passive: true })
    window.addEventListener('keydown', onKey)
  }

  function removeGlobals(): void {
    document.removeEventListener('pointerdown', hide, true)
    window.removeEventListener('scroll', hide, true)
    window.removeEventListener('keydown', onKey)
  }

  function show(text: string, ev: MouseEvent | FocusEvent): void {
    if (!canHover()) return
    state.text = text
    // Mouse events anchor to the cursor; keyboard focus (no cursor coords)
    // anchors to the top-center of the focused element instead.
    if ('clientX' in ev && (ev.clientX !== 0 || ev.clientY !== 0)) {
      state.x = ev.clientX
      state.y = ev.clientY
    } else {
      const el = ev.currentTarget as HTMLElement | null
      const rect = el?.getBoundingClientRect()
      state.x = rect ? rect.left + rect.width / 2 : 0
      state.y = rect ? rect.top : 0
    }
    // show() fires on every mousemove; only flip + bind listeners on the
    // hidden->visible edge so we don't add duplicate global handlers.
    if (!state.visible) {
      state.visible = true
      addGlobals()
    }
  }

  function hide(): void {
    if (!state.visible) return
    state.visible = false
    removeGlobals()
  }

  // Clean up if the owning component unmounts while the bubble is still up.
  // failSilently: this composable is also called bare in unit tests (no scope).
  onScopeDispose(removeGlobals, true)

  return { state, show, hide }
}
