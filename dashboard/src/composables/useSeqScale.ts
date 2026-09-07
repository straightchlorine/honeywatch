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

export function seq(t: number): string {
  const clamped = Math.max(0, Math.min(1, t))
  const x = clamped * (RAMP.length - 1)
  const i = Math.min(RAMP.length - 2, Math.floor(x))
  const f = x - i
  const a = hexToRgb(RAMP[i]!)
  const b = hexToRgb(RAMP[i + 1]!)
  const c = a.map((v, j) => Math.round(v + (b[j]! - v) * f))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

/** Log-scale t for heavy-tailed distributions. */
export function logT(v: number, max: number): number {
  return v <= 0 || max <= 0 ? 0 : Math.log1p(v) / Math.log1p(max)
}

/** Threshold above which dark ink meets WCAG contrast (--text / --bg-1) on seq(t). */
export const INK_FLIP_T = 0.37
export function needsDarkInk(t: number): boolean {
  return t >= INK_FLIP_T
}

export function useSeqScale(maxRef: MaybeRefOrGetter<number>) {
  const max = computed(() => toValue(maxRef))

  function color(value: number, pow = 1): string {
    const t = logT(value, max.value)
    return seq(pow === 1 ? t : Math.pow(t, pow))
  }

  return { color, logT, seq }
}
