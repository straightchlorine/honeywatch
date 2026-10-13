<script setup lang="ts">
  /**
   * Credentials "combination comb": hex matrix of username (rows) by
   * password (columns); fill = attempts, a ring = accepted. Rows/columns
   * are pruned to the OBSERVED universe (from `pairs`, not the raw top-N
   * lists); a cell that survives pruning but has no pair renders empty -
   * never a fabricated co-occurrence.
   */
  import { computed, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
  import { useReducedMotion } from '@/composables/useReducedMotion'
  import { hexPoints } from '@/utils/hex'
  import { seq, inkFor } from '@/composables/useSeqScale'
  import { useHwTooltip, type TooltipRow } from '@/composables/useHwTooltip'
  import { useRovingGrid } from '@/composables/useRovingGrid'
  import HexFocusRing from '@/components/base/HexFocusRing.vue'
  import { fmtCompact, fmtNumber } from '@/utils/format'

  export interface MatrixEntity {
    label: string
    count: number
  }

  export interface MatrixPair {
    username: string
    password: string
    count: number
    accepted: boolean
  }

  /** Payload for `select` - emitted for observed and unobserved cells alike. */
  export interface MatrixCellSelection {
    username: string
    password: string
    count: number
    accepted: boolean
    observed: boolean
  }

  const props = defineProps<{
    users: MatrixEntity[]
    passwords: MatrixEntity[]
    pairs: MatrixPair[]
    /** Selected cell's key (`${username}|${password}`); unset/null = none selected. */
    selectedKey?: string | null
  }>()

  const emit = defineEmits<{
    select: [cell: MatrixCellSelection]
    /** Fires whenever the fit-driven column count changes - the caller needs
     *  the actual drawn count, not the top-N fetch limit. */
    shown: [count: number]
  }>()

  const tooltip = useHwTooltip()
  const reduced = useReducedMotion()

  // PY/HR are fixed: the select-ring's stroke fits inside the PY-2*HR
  // headroom, and growing HR would make adjacent hexes overlap. PX_BASE is
  // just a floor - `px` below stretches to fill available width.
  const PX_BASE = 37
  const PY = 40
  const HR = 16.6

  // Labels render at a fixed on-screen size (the svg scales with its viewBox,
  // so the unit size is px / scale; see `scale`). Metrics are measured against
  // the live --font-mono stack (monospace, so one advance fits every char),
  // in em: 7px/char advance, 12/3 ascent/descent at 11.5px, regardless of
  // content.
  const AXIS_PX = 12
  const CELL_PX = 12
  const AXIS_CHAR_EM = 0.61
  const AXIS_ASCENT_EM = 1.04
  const AXIS_DESCENT_EM = 0.26
  const AXIS_ROTATE_DEG = 38
  const AXIS_COS = Math.cos((AXIS_ROTATE_DEG * Math.PI) / 180)
  const AXIS_SIN = Math.sin((AXIS_ROTATE_DEG * Math.PI) / 180)
  // Antialiasing/hinting nudges glyphs past their measured width; this
  // absorbs that residue instead of padding by guesswork.
  const AXIS_SAFETY_EM = 0.35
  // Fixed breathing room between a label's anchor and the grid it labels.
  const ROW_LABEL_GAP = 12
  const COL_LABEL_GAP = 10
  // Headroom for a cell's own overshoot (hex vertex / select-ring stroke).
  const CELL_TOP_PAD = 4

  // Caps axis labels so two different long values never render as
  // identical text; the marker signals "this was cut" rather than
  // silently dropping the tail.
  const MAX_LABEL_CHARS = 8
  // \u2026 escape keeps this source file ASCII-only (scripts/check-ascii.mjs)
  // while still producing a real ellipsis at runtime.
  const TRUNC_MARKER = '\u2026'

  /** Caps a label at MAX_LABEL_CHARS for DISPLAY only - tooltip, aria-label,
   *  and the `select` payload always get the real value. */
  function truncateLabel(label: string): string {
    return label.length > MAX_LABEL_CHARS
      ? `${label.slice(0, MAX_LABEL_CHARS - 1)}${TRUNC_MARKER}`
      : label
  }

  /** How far a right-anchored row label reaches left of its anchor - capped
   *  text width plus the safety margin. */
  function rowLabelReach(charCount: number, fs: number): number {
    return (Math.min(charCount, MAX_LABEL_CHARS) * AXIS_CHAR_EM + AXIS_SAFETY_EM) * fs
  }

  /** Reach of a rotated (-AXIS_ROTATE_DEG), end-anchored column label past
   *  its anchor: top-left corner -> `left` (feeds GX), bottom-left ->
   *  `bottom` (feeds GY), bottom-right -> `right` (charCount-independent). */
  function colLabelReach(
    charCount: number,
    fs: number,
  ): { left: number; right: number; bottom: number } {
    const w = Math.min(charCount, MAX_LABEL_CHARS) * AXIS_CHAR_EM
    return {
      left: (w * AXIS_COS + AXIS_ASCENT_EM * AXIS_SIN + AXIS_SAFETY_EM) * fs,
      right: (AXIS_DESCENT_EM * AXIS_SIN + AXIS_SAFETY_EM) * fs,
      bottom: (w * AXIS_SIN + AXIS_DESCENT_EM * AXIS_COS + AXIS_SAFETY_EM) * fs,
    }
  }

  // Order is inherited from props.users/passwords (already count-desc), so
  // slicing later keeps that ranking.
  const candidateUsers = computed(() => {
    const withPair = new Set(props.pairs.map((p) => p.username))
    return props.users.filter((u) => withPair.has(u.label)).slice(0, phoneCap.value)
  })
  const candidatePasswords = computed(() => {
    const withPair = new Set(props.pairs.map((p) => p.password))
    return props.passwords.filter((p) => withPair.has(p.label)).slice(0, phoneCap.value)
  })

  // Sized off the CANDIDATE lists (pre-fit), not displayed* - GX/GY must
  // never depend on `cols`, or we'd create a height->scale->cols->rows
  // feedback loop. A displayed label is always a subset, so this only ever
  // over-allocates a few unused px.
  const maxUserChars = computed(() => {
    let m = 0
    for (const u of candidateUsers.value) m = Math.max(m, u.label.length)
    return m
  })
  const maxPasswordChars = computed(() => {
    let m = 0
    for (const p of candidatePasswords.value) m = Math.max(m, p.label.length)
    return m
  })

  /** Row-label gutter: fits the longest candidate username, or column 0's
   *  rotated label off the viewBox's left edge - whichever needs more. */
  const GX = computed(() => {
    const forRowLabels = ROW_LABEL_GAP + rowLabelReach(maxUserChars.value, axisFs.value)
    const forColumnZero = colLabelReach(maxPasswordChars.value, axisFs.value).left - PX_BASE / 2
    return Math.max(forRowLabels, forColumnZero)
  })
  /** Column-label band below the grid, sized to the longest candidate
   *  password's rotated label. */
  const GY = computed(
    () => COL_LABEL_GAP + colLabelReach(maxPasswordChars.value, axisFs.value).bottom,
  )

  // svg is flex:1/min-height:0 inside the card, so its box never depends on
  // our viewBox - safe to observe.
  const svgEl = useTemplateRef('svg')
  const boxW = ref(0)
  const boxH = ref(0)
  // Phone-width cards get a square top-N grid (rows and columns) so labels
  // and cells stay legible; chosen from the measured width, not the device.
  const PHONE_MAX_W = 520
  const PHONE_NARROW_W = 310
  const phoneCap = computed(() => {
    if (boxW.value <= 0 || boxW.value >= PHONE_MAX_W) return Infinity
    return boxW.value < PHONE_NARROW_W ? 4 : 5
  })
  let ro: ResizeObserver | null = null
  onMounted(() => {
    if (!svgEl.value) return
    ro = new ResizeObserver(([entry]) => {
      boxW.value = entry?.contentRect.width ?? 0
      boxH.value = entry?.contentRect.height ?? 0
    })
    ro.observe(svgEl.value)
  })
  onUnmounted(() => ro?.disconnect())

  // Rendered scale (px per viewBox unit) the column fit assumes: the svg is
  // height-bound on the CANDIDATE rows (reading displayedUsers would make
  // sizing depend on `cols` and spin). Label unit size is AXIS_PX / scale and
  // the label band grows with it, so scale = boxH / (a + k * AXIS_PX / scale);
  // solve it in closed form rather than iterate. 1 until measured.
  const scale = computed(() => {
    if (!Number.isFinite(boxH.value) || boxH.value <= 0) return 1
    const a = CELL_TOP_PAD + candidateUsers.value.length * PY + COL_LABEL_GAP
    const k = colLabelReach(maxPasswordChars.value, 1).bottom
    return Math.max(0.3, (boxH.value - AXIS_PX * k) / a)
  })
  const axisFs = computed(() => AXIS_PX / scale.value)

  // Columns that fit at the card's live size: how many PX_BASE-wide columns fit
  // in width at `scale`. Falls back to every candidate column pre-measurement
  // (first paint, or jsdom's no-op RO stub).
  const cols = computed(() => {
    // Check finiteness before dividing - NaN would slip past a falsy check.
    if (!Number.isFinite(boxW.value) || !Number.isFinite(boxH.value)) {
      return candidatePasswords.value.length
    }
    if (boxW.value <= 0 || boxH.value <= 0) return candidatePasswords.value.length
    // Estimate only - charCount-independent, so using maxPasswordChars here
    // (before displayedPasswords is known) can't skew it.
    const estimatedRightPad = colLabelReach(maxPasswordChars.value, axisFs.value).right
    const raw = Math.floor((boxW.value / scale.value - GX.value - estimatedRightPad) / PX_BASE)
    return Math.min(candidatePasswords.value.length, Math.max(6, raw))
  })
  // candidatePasswords arrive sorted by count desc, so slicing from the front
  // keeps the most-attempted columns when width can't fit them all.
  const displayedPasswords = computed(() => candidatePasswords.value.slice(0, cols.value))

  // A candidate user only earns a drawn row if it has an observed pair among
  // the columns actually drawn - otherwise column-fit slicing could leave
  // an all-empty row.
  // .reverse(): the most-attempted username belongs at the bottom (dense
  // corner), but rowY() grows top-down - reversing the array (not rowY)
  // keeps DOM order matching visual order for screen readers.
  const displayedUsers = computed(() => {
    if (displayedPasswords.value.length === 0) return []
    const shownPw = new Set(displayedPasswords.value.map((p) => p.label))
    const usersWithShownPair = new Set(
      props.pairs.filter((p) => shownPw.has(p.password)).map((p) => p.username),
    )
    return candidateUsers.value.filter((u) => usersWithShownPair.has(u.label)).reverse()
  })

  // `cols` is a whole number so PX_BASE rarely divides available width
  // exactly; stretch the pitch to consume the leftover once displayedPasswords
  // is fixed. Clamped to never go below PX_BASE.
  const px = computed(() => {
    if (
      displayedPasswords.value.length === 0 ||
      !Number.isFinite(boxW.value) ||
      !Number.isFinite(boxH.value) ||
      boxW.value <= 0 ||
      boxH.value <= 0
    ) {
      return PX_BASE
    }
    const available = boxW.value / scale.value
    let bound = Infinity
    displayedPasswords.value.forEach((p, j) => {
      const reach = colLabelReach(p.label.length, axisFs.value).right
      bound = Math.min(bound, (available - GX.value - reach) / (j + 0.5))
    })
    return Number.isFinite(bound) ? Math.max(PX_BASE, bound) : PX_BASE
  })

  // Max of the grid's own right edge and every DISPLAYED column's rotated
  // label reach, checked per-column. Uses stretched `px`, not PX_BASE.
  const width = computed(() => {
    const gridRight = GX.value + displayedPasswords.value.length * px.value
    let maxLabelRight = gridRight
    displayedPasswords.value.forEach((p, j) => {
      maxLabelRight = Math.max(
        maxLabelRight,
        colX(j) + colLabelReach(p.label.length, axisFs.value).right,
      )
    })
    return maxLabelRight
  })
  // Grid's actual (post-fit) bottom edge; height and colLabelY key off this,
  // not the pre-fit candidate height. Driven by displayedUsers, so a rare
  // pruning-after-fit frame may letterbox slightly rather than reopen the
  // cols loop.
  const gridBottom = computed(() => CELL_TOP_PAD + displayedUsers.value.length * PY)
  const height = computed(() => gridBottom.value + GY.value)
  // Column labels sit just below the grid's actual (post-fit) bottom edge.
  const colLabelY = computed(() => gridBottom.value + COL_LABEL_GAP)

  watch(
    () => displayedPasswords.value.length,
    (n) => emit('shown', n),
    { immediate: true },
  )

  // In-cell counts render at CELL_PX; when the longest one is wider than the
  // hex there, drop them all and let fill/tooltip/drawer carry the number.
  const cellFs = computed(() => CELL_PX / scale.value)
  const showLabels = computed(() => {
    if (!Number.isFinite(boxH.value) || boxH.value <= 0) return true
    const chars = Math.max(0, ...cells.value.map((c) => label(c).length))
    return chars * AXIS_CHAR_EM * cellFs.value <= HR * 1.6
  })

  function colX(j: number): number {
    return GX.value + j * px.value + px.value / 2
  }
  function rowY(i: number): number {
    return CELL_TOP_PAD + i * PY + PY / 2
  }

  interface Cell {
    key: string
    x: number
    y: number
    n: number
    observed: boolean
    accepted: boolean
    username: string
    password: string
  }

  // JSON tuples for lookup and v-for keys: labels may hold any separator.
  const cells = computed<Cell[]>(() => {
    const real = new Map(props.pairs.map((p) => [JSON.stringify([p.username, p.password]), p]))
    const out: Cell[] = []
    displayedUsers.value.forEach((u, i) => {
      const y = rowY(i)
      displayedPasswords.value.forEach((p, j) => {
        const x = colX(j)
        const hit = real.get(JSON.stringify([u.label, p.label]))
        out.push({
          key: JSON.stringify([u.label, p.label]),
          x,
          y,
          n: hit?.count ?? 0,
          observed: hit !== undefined,
          accepted: hit?.accepted ?? false,
          username: u.label,
          password: p.label,
        })
      })
    })
    return out
  })

  // Calibrated against observed cells only - an unobserved cell must never
  // brighten (or dim) the ramp for the cells that do have real data.
  const maxCell = computed(() => {
    let m = 1
    for (const c of cells.value) if (c.observed) m = Math.max(m, c.n)
    return m
  })

  /** Normalized 0..1 heat for a cell. */
  function heat(c: Cell): number {
    return c.observed && c.n > 0 ? Math.pow(c.n / maxCell.value, 0.45) : 0
  }
  function fill(c: Cell): string {
    return c.observed && c.n > 0 ? seq(heat(c)) : 'var(--surface-2)'
  }
  // In-cell count takes whichever ink contrasts best with its fill (WCAG).
  function ink(c: Cell): string {
    return inkFor(heat(c))
  }
  // selectedKey is `${username}|${password}` (set by the caller), so compare
  // against that format rather than the JSON cell key.
  function isSelected(c: Cell): boolean {
    return props.selectedKey === `${c.username}|${c.password}`
  }
  function label(c: Cell): string {
    return c.observed ? fmtCompact(c.n) : ''
  }
  function ariaLabel(c: Cell): string {
    if (!c.observed) return `${c.username} with password ${c.password}: never tried`
    return `${c.username} with password ${c.password}: ${fmtNumber(c.n)} attempts${c.accepted ? ', accepted' : ''}`
  }
  function tip(c: Cell): [string, TooltipRow[]] {
    return [
      `${c.username}:${c.password}`,
      c.observed
        ? [
            ['Attempts', fmtNumber(c.n)],
            ['Outcome', c.accepted ? 'accepted' : 'rejected'],
          ]
        : [['Outcome', 'never tried']],
    ]
  }

  function selectCell(c: Cell): void {
    emit('select', {
      username: c.username,
      password: c.password,
      count: c.n,
      accepted: c.accepted,
      observed: c.observed,
    })
  }
  const { tabKey, ring, onFocus, onBlur, onKeydown } = useRovingGrid({
    cells,
    cols: () => displayedPasswords.value.length,
    home: () => cells.value.reduce<Cell | null>((b, c) => (!b || c.n > b.n ? c : b), null)?.key,
    geom: (c) => ({ cx: c.x, cy: c.y, r: HR }),
    tip,
    activate: selectCell,
  })

  function cellDelay(idx: number): string {
    return reduced.value ? '0ms' : `${idx * 12}ms`
  }
</script>

<template>
  <!-- role="img" forbids interactive descendants (axe: aria-prohibited-attr) -
       the focusable cells need the ARIA Graphics Module's "graphics-document"
       role instead (mirrors WorldMap.vue). -->
  <svg
    ref="svg"
    class="hex-matrix"
    role="graphics-document"
    aria-label="Grid of username and password pairs, shaded by how often each was tried. Exact counts are in the What worked list."
    :viewBox="`0 0 ${width} ${height}`"
  >
    <!-- End-anchored so the label's last character sits nearest its column;
         aria-label carries the full value since the visible text is capped. -->
    <text
      v-for="(p, j) in displayedPasswords"
      :key="`col-${p.label}`"
      class="mx-axis"
      text-anchor="end"
      :aria-label="p.label"
      :font-size="axisFs"
      :x="colX(j)"
      :y="colLabelY"
      :transform="`rotate(-${AXIS_ROTATE_DEG} ${colX(j)} ${colLabelY})`"
    >
      {{ truncateLabel(p.label) }}
    </text>
    <text
      v-for="(u, i) in displayedUsers"
      :key="`row-${u.label}`"
      class="mx-axis"
      text-anchor="end"
      :aria-label="u.label"
      :font-size="axisFs"
      :x="GX - ROW_LABEL_GAP"
      :y="rowY(i) + axisFs * 0.35"
    >
      {{ truncateLabel(u.label) }}
    </text>

    <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
    <g v-for="(c, idx) in cells" :key="c.key">
      <polygon
        class="mcell"
        :points="hexPoints(c.x, c.y, HR)"
        :fill="fill(c)"
        :stroke="c.accepted ? 'var(--ok)' : 'none'"
        :stroke-width="c.accepted ? 1.8 : 0"
        :style="{ animationDelay: cellDelay(idx) }"
        :tabindex="c.key === tabKey ? 0 : -1"
        role="button"
        :aria-label="ariaLabel(c)"
        @pointerenter="tooltip.show(...tip(c), undefined, $event)"
        @pointermove="tooltip.move($event)"
        @pointerleave="tooltip.hide()"
        @focus="onFocus(c, $event)"
        @blur="onBlur"
        @click="selectCell(c)"
        @keydown="onKeydown(c, $event)"
      />
      <!-- Non-colour "accepted" cue: a solid dot near the top vertex (survives at mobile hex size). -->
      <circle
        v-if="c.accepted"
        class="mx-accept-dot"
        :cx="c.x"
        :cy="c.y - HR * 0.62"
        r="2.6"
        :style="{ animationDelay: cellDelay(idx) }"
        aria-hidden="true"
      />
      <text
        v-if="showLabels && label(c)"
        class="mx-cell-label"
        :style="{ fill: ink(c), animationDelay: cellDelay(idx) }"
        text-anchor="middle"
        :font-size="cellFs"
        :x="c.x"
        :y="c.y + cellFs * 0.36"
        aria-hidden="true"
      >
        {{ label(c) }}
      </text>
      <polygon
        v-if="isSelected(c)"
        class="mx-select-ring"
        :points="hexPoints(c.x, c.y, HR)"
        fill="none"
        aria-hidden="true"
      />
    </g>
    <HexFocusRing v-if="ring" v-bind="ring" />
    <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
  </svg>
</template>

<style scoped>
  .hex-matrix {
    display: block;
    width: 100%;
    overflow: visible;
  }

  .mx-axis {
    fill: var(--text-muted);
    font-family: var(--font-mono);
  }

  .mx-cell-label {
    fill: var(--text);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
    /* Same entrance and delay as its cell, so the number does not hang in place while the hex flies in. */
    animation: mcell-in 280ms ease-out both;
  }

  .mx-accept-dot {
    fill: var(--ok);
    pointer-events: none;
    animation: mcell-in 280ms ease-out both;
  }

  .mx-select-ring {
    stroke: var(--accent-hot);
    stroke-width: 2.5;
    pointer-events: none;
  }

  .mcell {
    transition: filter var(--motion-fast);
    cursor: pointer;
    animation: mcell-in 280ms ease-out both;
  }

  .mcell:hover {
    filter: brightness(1.5);
  }

  .mcell:focus {
    outline: none;
  }

  @keyframes mcell-in {
    from {
      opacity: 0;
      transform: scale(0.85);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .mcell,
    .mx-accept-dot,
    .mx-cell-label {
      animation: none;
    }
  }
</style>
