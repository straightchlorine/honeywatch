/** Pointy-top hexagon vertices as an SVG `points` string, one point per 60deg. */
export function hexPoints(cx: number, cy: number, r: number): string {
  const pts: string[] = []
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i - 30)
    pts.push(`${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`)
  }
  return pts.join(' ')
}
