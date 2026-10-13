import { computed, toValue, type MaybeRefOrGetter } from 'vue'

/**
 * Sequential amber ramp: dark recedes, bright reads as hot. Interpolated
 * across stops rather than CSS gradients since SVG paths cannot use
 * CSS custom-property gradients, ensuring single numeric t always maps to
 * an exact color.
 */
const RAMP = ['#78350f', '#92400e', '#b45309', '#d97706', '#f59e0b', '#fbbf24', '#fde68a']

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function seqRgb(t: number): number[] {
  const clamped = Math.max(0, Math.min(1, t))
  const x = clamped * (RAMP.length - 1)
  const i = Math.min(RAMP.length - 2, Math.floor(x))
  const f = x - i
  const a = hexToRgb(RAMP[i]!)
  const b = hexToRgb(RAMP[i + 1]!)
  return a.map((v, j) => Math.round(v + (b[j]! - v) * f))
}

export function seq(t: number): string {
  const c = seqRgb(t)
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

/** Log-scale t for heavy-tailed distributions. */
export function logT(v: number, max: number): number {
  return v <= 0 || max <= 0 ? 0 : Math.log1p(v) / Math.log1p(max)
}

// Ink candidates, mirrored from tokens.css: --text (light) and --bg-0 (dark), drift-checked in tests.
// pure white/black cover the narrow mid-ramp band (t ~0.27-0.40)
// where neither token ink reaches 4.5:1 (best token ratio there is ~4.0).
const INK_LIGHT = '#f5e6c8'
const INK_DARK = '#120d09'
const INK_BLACK = '#000000'
const INK_WHITE = '#ffffff'

function lum(rgb: number[]): number {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
}

/** WCAG contrast ratio of an ink hex on seq(t). */
export function inkContrast(ink: string, t: number): number {
  const a = lum(seqRgb(t)) + 0.05
  const b = lum(hexToRgb(ink)) + 0.05
  return a > b ? a / b : b / a
}

/** Ink hex with the best contrast on seq(t): the token inks first, pure black/white only if both miss 4.5. */
export function inkFor(t: number): string {
  const best = inkContrast(INK_DARK, t) > inkContrast(INK_LIGHT, t) ? INK_DARK : INK_LIGHT
  if (inkContrast(best, t) >= 4.5) return best
  return inkContrast(INK_BLACK, t) > inkContrast(INK_WHITE, t) ? INK_BLACK : INK_WHITE
}

export function useSeqScale(maxRef: MaybeRefOrGetter<number>) {
  const max = computed(() => toValue(maxRef))

  function color(value: number, pow = 1): string {
    const t = logT(value, max.value)
    return seq(pow === 1 ? t : Math.pow(t, pow))
  }

  return { color, logT, seq }
}
