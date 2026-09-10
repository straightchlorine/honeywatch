/**
 * Scales bar fractions linearly against the list maximum.
 *
 * Bars are read as proportional, so they must be: the old p75*1.5 cap clamped
 * every value above it to a full bar, making the two largest rows
 * indistinguishable. The tail is short by design; each row prints its true value.
 */
export function cappedFracs(values: number[]): {
  frac: (n: number) => number
} {
  const max = Math.max(0, ...values.filter((n) => n > 0))
  const denom = max > 0 ? max : 1
  return {
    frac: (n) => Math.min(1, Math.max(0, n / denom)),
  }
}
