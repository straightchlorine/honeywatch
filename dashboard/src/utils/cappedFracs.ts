/**
 * Scales bar fractions against p75*1.5 for heavy-tailed data.
 *
 * Linear scaling collapses when top values dwarf the 75th percentile. We scale
 * against p75*1.5 instead and flag rows exceeding this cap. p75 is used (not p90)
 * because these lists hold ~10-25 rows, where p90 often equals the max. Bar length
 * must stay proportional to value (never log scale) or visual comparison breaks.
 * Row labels always show the true value.
 */
export function cappedFracs(values: number[]): {
  frac: (n: number) => number
  over: (n: number) => boolean
} {
  const sorted = [...values].filter((n) => n > 0).sort((a, b) => a - b)
  const rawMax = sorted[sorted.length - 1] ?? 0
  const p75 = sorted[Math.max(0, Math.ceil(sorted.length * 0.75) - 1)] ?? 0
  const capped = p75 > 0 && rawMax > 3 * p75
  const ceil = capped ? Math.min(rawMax, p75 * 1.5) : rawMax
  const denom = ceil > 0 ? ceil : 1
  return {
    frac: (n) => Math.min(1, n / denom),
    over: (n) => capped && n > ceil,
  }
}
