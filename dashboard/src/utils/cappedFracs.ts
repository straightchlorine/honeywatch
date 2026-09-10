/**
 * Scales bar fractions linearly against the list maximum.
 *
 * Bar length is read as proportional to value, so it must be. An earlier
 * version scaled against p75*1.5 to keep the tail legible, but that clamped
 * every value above the cap to a full bar: on the SSH-client list, 6.7k and
 * 4.6k both rendered at 100% while 292 rendered at two thirds. Compressing the
 * tail is a tradeoff; making the two largest rows indistinguishable is a lie,
 * and it lands on exactly the rows read first.
 *
 * The tail is now short by design. RankList floors the width at 2% so no row
 * vanishes, and every row prints its true value at the right edge.
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
