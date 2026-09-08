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
  import { seq, needsDarkInk } from '@/composables/useSeqScale'
  import { useHwTooltip } from '@/composables/useHwTooltip'
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

  // Measured against the live --font-mono stack (monospace, so one width
  // fits every char): 7px/char advance, 12/3 ascent/descent regardless of
  // content.
  const AXIS_CHAR_W = 7
  const AXIS_ASCENT = 12
  const AXIS_DESCENT = 3
  const AXIS_ROTATE_DEG = 38
  const AXIS_COS = Math.cos((AXIS_ROTATE_DEG * Math.PI) / 180)
  const AXIS_SIN = Math.sin((AXIS_ROTATE_DEG * Math.PI) / 180)
  // Antialiasing/hinting nudges glyphs past their measured width; this
  // absorbs that residue instead of padding by guesswork.
  const AXIS_SAFETY = 4
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
  function rowLabelReach(charCount: number): number {
    return Math.min(charCount, MAX_LABEL_CHARS) * AXIS_CHAR_W + AXIS_SAFETY
  }

  /** Reach of a rotated (-AXIS_ROTATE_DEG), end-anchored column label past
   *  its anchor: top-left corner -> `left` (feeds GX), bottom-left ->
   *  `bottom` (feeds GY), bottom-right -> `right` (charCount-independent). */
  function colLabelReach(charCount: number): { left: number; right: number; bottom: number } {
    const w = Math.min(charCount, MAX_LABEL_CHARS) * AXIS_CHAR_W
    return {
      left: w * AXIS_COS + AXIS_ASCENT * AXIS_SIN + AXIS_SAFETY,
      right: AXIS_DESCENT * AXIS_SIN + AXIS_SAFETY,
      bottom: w * AXIS_SIN + AXIS_DESCENT * AXIS_COS + AXIS_SAFETY,
    }
  }

  // Order is inherited from props.users/passwords (already count-desc), so
  // slicing later keeps that ranking.
  const candidateUsers = computed(() => {
    const withPair = new Set(props.pairs.map((p) => p.username))
    return props.users.filter((u) => withPair.has(u.label))
  })
  const candidatePasswords = computed(() => {
    const withPair = new Set(props.pairs.map((p) => p.password))
    return props.passwords.filter((p) => withPair.has(p.label))
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
    const forRowLabels = ROW_LABEL_GAP + rowLabelReach(maxUserChars.value)
    const forColumnZero = colLabelReach(maxPasswordChars.value).left - PX_BASE / 2
    return Math.max(forRowLabels, forColumnZero)
  })
  /** Column-label band below the grid, sized to the longest candidate
   *  password's rotated label. */
  const GY = computed(() => COL_LABEL_GAP + colLabelReach(maxPasswordChars.value).bottom)

  // Feeds only the column-fit scale below - reading displayedUsers here would
  // make sizing depend on `cols` and spin.
  const scaleHeight = computed(() => CELL_TOP_PAD + candidateUsers.value.length * PY + GY.value)

  // svg is flex:1/min-height:0 inside the card, so its box never depends on
  // our viewBox - safe to observe.
  const svgEl = useTemplateRef('svg')
  const boxW = ref(0)
  const boxH = ref(0)
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

  // Columns that fit at the card's live size: derive scale from scaleHeight,
  // then how many PX_BASE-wide columns fit in width. Falls back to every
  // candidate column pre-measurement (first paint, or jsdom's no-op RO stub).
  const cols = computed(() => {
    // Check finiteness before dividing - NaN would slip past a falsy check.
    if (!Number.isFinite(boxW.value) || !Number.isFinite(boxH.value)) {
      return candidatePasswords.value.length
    }
    if (boxW.value <= 0 || boxH.value <= 0) return candidatePasswords.value.length
    const scale = boxH.value / scaleHeight.value
    // Estimate only - charCount-independent, so using maxPasswordChars here
    // (before displayedPasswords is known) can't skew it.
    const estimatedRightPad = colLabelReach(maxPasswordChars.value).right
    const raw = Math.floor((boxW.value / scale - GX.value - estimatedRightPad) / PX_BASE)
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
    const scale = boxH.value / scaleHeight.value
    const available = boxW.value / scale
    let bound = Infinity
    displayedPasswords.value.forEach((p, j) => {
      const reach = colLabelReach(p.label.length).right
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
      maxLabelRight = Math.max(maxLabelRight, colX(j) + colLabelReach(p.label.length).right)
    })
    return maxLabelRight
  })
  // Grid's actual (post-fit) bottom edge; height and colLabelY key off this,
  // not the pre-fit scaleHeight. Driven by displayedUsers, so a rare
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

  // In-cell count is 8px in viewBox units; below ~9px on-screen it's mush -
  // drop it and let fill/tooltip/drawer carry the number instead.
  const LABEL_MIN_SCALE = 9 / 8
  const showLabels = computed(() => {
    if (!Number.isFinite(boxH.value) || boxH.value <= 0) return true
    return boxH.value / height.value >= LABEL_MIN_SCALE
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

  const cells = computed<Cell[]>(() => {
    const real = new Map(props.pairs.map((p) => [`${p.username} ${p.password}`, p]))
    const out: Cell[] = []
    displayedUsers.value.forEach((u, i) => {
      const y = rowY(i)
      displayedPasswords.value.forEach((p, j) => {
        const x = colX(j)
        const hit = real.get(`${u.label} ${p.label}`)
        out.push({
          key: `${u.label}|${p.label}`,
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
  // In-cell count flips to dark ink when the fill is bright enough that
  // light text would fail contrast.
  function isDark(c: Cell): boolean {
    return needsDarkInk(heat(c))
  }
  function label(c: Cell): string {
    return c.observed ? fmtCompact(c.n) : ''
  }
  function ariaLabel(c: Cell): string {
    if (!c.observed) return `${c.username} with password ${c.password}: never tried`
    return `${c.username} with password ${c.password}: ${fmtNumber(c.n)} attempts${c.accepted ? ', accepted' : ''}`
  }
  function showTooltip(c: Cell, e: { clientX?: number; clientY?: number }): void {
    tooltip.show(
      `${c.username}:${c.password}`,
      c.observed
        ? [
            ['Attempts', fmtNumber(c.n)],
            ['Outcome', c.accepted ? 'accepted' : 'rejected'],
          ]
        : [['Outcome', 'never tried']],
    )
    if (e.clientX !== undefined && e.clientY !== undefined) {
      tooltip.move({ clientX: e.clientX, clientY: e.clientY })
    }
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
  function onKeydown(c: Cell, e: KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      selectCell(c)
    }
  }

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
      :x="GX - ROW_LABEL_GAP"
      :y="rowY(i) + 4"
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
        tabindex="0"
        role="button"
        :aria-label="ariaLabel(c)"
        @pointerenter="showTooltip(c, $event)"
        @pointermove="tooltip.move($event)"
        @pointerleave="tooltip.hide()"
        @focus="showTooltip(c, {})"
        @blur="tooltip.hide()"
        @click="selectCell(c)"
        @keydown="onKeydown(c, $event)"
      />
      <text
        v-if="showLabels && label(c)"
        class="mx-cell-label"
        :class="{ dark: isDark(c) }"
        text-anchor="middle"
        :x="c.x"
        :y="c.y + 3"
        aria-hidden="true"
      >
        {{ label(c) }}
      </text>
      <polygon
        v-if="c.key === selectedKey"
        class="mx-select-ring"
        :points="hexPoints(c.x, c.y, HR)"
        fill="none"
        aria-hidden="true"
      />
    </g>
    <!-- eslint-enable vuejs-accessibility/mouse-events-have-key-events, vuejs-accessibility/no-static-element-interactions -->
  </svg>
</template>

<style scoped>
  .hex-matrix {
    display: block;
    width: 100%;
  }

  .mx-axis {
    fill: var(--text-muted);
    font-size: 11.5px;
    font-family: var(--font-mono);
  }

  .mx-cell-label {
    fill: var(--text);
    font-size: 8px;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }

  .mx-cell-label.dark {
    fill: var(--bg-1);
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

  .mcell:focus-visible {
    stroke: var(--accent-hot);
    stroke-width: 2;
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
    .mcell {
      animation: none;
    }
  }
</style>
