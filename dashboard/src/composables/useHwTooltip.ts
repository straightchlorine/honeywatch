/**
 * Singleton raw DOM node outside Vue tree to avoid re-rendering SVG on every
 * tooltip change; styled in assets/tokens.css and populated via textContent for
 * security (content is attacker-controlled).
 */
let el: HTMLDivElement | null = null
let shownAt = 0

function ensure(): HTMLDivElement {
  if (el) return el
  el = document.createElement('div')
  el.className = 'hw-tooltip'
  document.body.appendChild(el)
  return el
}

// On touch devices, taps fire pointerenter and pointerleave in one burst;
// keep bubble visible until next tap elsewhere or scroll (tap-to-peek).
// Guard matchMedia for jsdom.
function touchPrimary(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(hover: none)').matches
}

// Pointerdown/pointerleave fire right after show(); ignore unforced hides
// within this window so the bubble survives the tap.
const TAP_BURST_MS = 350

function onGlobalDown(): void {
  hideNode(false)
}
function onGlobalScroll(): void {
  hideNode(true)
}
function addGlobals(): void {
  document.addEventListener('pointerdown', onGlobalDown, true)
  window.addEventListener('scroll', onGlobalScroll, { capture: true, passive: true })
}
function removeGlobals(): void {
  document.removeEventListener('pointerdown', onGlobalDown, true)
  window.removeEventListener('scroll', onGlobalScroll, true)
}

function hideNode(force: boolean): void {
  if (!force && touchPrimary() && performance.now() - shownAt < TAP_BURST_MS) return
  removeGlobals()
  el?.classList.remove('show')
}

export type TooltipRow = [string, string, ('pos' | 'neg')?]

export function useHwTooltip() {
  function show(title: string, rows: TooltipRow[] = [], icon?: string): void {
    const node = ensure()
    node.replaceChildren()

    const head = document.createElement('div')
    head.className = 'tt-title'
    if (icon) {
      const ic = document.createElement('span')
      ic.textContent = icon
      head.appendChild(ic)
    }
    head.appendChild(document.createTextNode(title))
    node.appendChild(head)

    for (const [label, value, variant] of rows) {
      const row = document.createElement('div')
      row.className = 'tt-row'
      const l = document.createElement('span')
      l.textContent = label
      const v = document.createElement('b')
      if (variant) v.classList.add(`tt-${variant}`)
      v.textContent = value
      row.append(l, v)
      node.appendChild(row)
    }
    node.classList.add('show')
    shownAt = performance.now()
    if (touchPrimary()) addGlobals()
  }

  function move(e: { clientX: number; clientY: number }): void {
    const node = ensure()
    const pad = 14
    const w = node.offsetWidth
    const h = node.offsetHeight
    let x = e.clientX + pad
    let y = e.clientY + pad
    if (x + w > window.innerWidth - 8) x = e.clientX - w - pad
    if (y + h > window.innerHeight - 8) y = e.clientY - h - pad
    // Clamp to keep bubble fully visible when neither side has room.
    x = Math.max(8, Math.min(x, window.innerWidth - w - 8))
    y = Math.max(8, Math.min(y, window.innerHeight - h - 8))
    node.style.left = `${x}px`
    node.style.top = `${y}px`
  }

  /** `force` bypasses the tap-burst guard for programmatic hides that must win even mid-tap. */
  function hide(force = false): void {
    hideNode(force)
  }

  return { show, move, hide }
}
