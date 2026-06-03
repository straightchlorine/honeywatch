import type {
  CommandTacticResponse,
  TopCommandLineResponse,
  TopCommandResponse,
} from '@/api/generated/types.gen'
import { sanitizeAttackerText } from '@/utils/sanitize'
import { redactIps } from '@/utils/redactIps'
import { fmtNumber } from './format'
import { pctWidth, type BarRow } from './credentials'

const EMPTY = '‹empty›'

/** Human labels for the tactic buckets (the API emits the raw keys). */
export const TACTIC_LABELS: Record<string, string> = {
  recon: 'Recon',
  download: 'Download',
  execute: 'Execute',
  persist: 'Persist',
  destroy: 'Destroy',
  shell: 'Shell',
  other: 'Other',
}

/**
 * Neutralize an attacker command string for display: hex-escape control / bidi
 * code points (sanitize), then blot any IP literal. The API already redacts
 * server-side; redactIps here is idempotent (it recognizes the blot token) and
 * stays as defense-in-depth. allowWhitespace is false so a crafted TAB/newline
 * is escaped rather than breaking the single-line bar row (spaces are kept).
 */
function cleanCommand(raw: string): string {
  if (raw === '') return ''
  const escaped = sanitizeAttackerText(raw, { mode: 'escape', allowWhitespace: false })
  return redactIps(escaped).text
}

/** Top executables -> bar rows (label is the executable bucket). */
export function buildCommandRows(items: TopCommandResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it, idx) => {
    const label = cleanCommand(it.command) || EMPTY
    return {
      key: `${label}|${idx}`,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: `${label} — ${fmtNumber(it.count)}`,
    }
  })
}

/** Tactic breakdown -> bar rows (mapped to human labels). */
export function buildTacticRows(items: CommandTacticResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it) => {
    const label = TACTIC_LABELS[it.name] ?? it.name
    return {
      key: it.name,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: `${label} — ${fmtNumber(it.count)}`,
    }
  })
}

/** Compound one-liners -> bar rows (the verbatim dropper scripts). */
export function buildCommandLineRows(items: TopCommandLineResponse[]): BarRow[] {
  let max = 0
  for (const it of items) if (it.count > max) max = it.count
  return items.map((it, idx) => {
    const label = cleanCommand(it.input) || EMPTY
    return {
      key: `line-${idx}`,
      label,
      count: it.count,
      widthPct: pctWidth(it.count, max),
      title: label,
    }
  })
}
