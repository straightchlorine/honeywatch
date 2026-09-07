/**
 * Convert Alpha-2 code to flag emoji. Only flag emoji render
 * reliably cross-platform; other symbols use entities or SVG.
 */
export function useCountryFlag(a2: string | null | undefined): string {
  if (!a2 || a2.length !== 2) return '-'
  return String.fromCodePoint(...[...a2.toUpperCase()].map((c) => 127397 + c.charCodeAt(0)))
}
