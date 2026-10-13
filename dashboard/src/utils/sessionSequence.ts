import type { ListSessionsResponse, SessionSummaryResponse } from '@/api/generated/types.gen'

export type SequenceRow = SessionSummaryResponse

// The sessions in the order they sit on the phone list: each row, then the cached members of the
// runs the list had open (?run= names their first ids). A run page that is not cached stops that
// run's members there, so the chain never offers a neighbour it cannot place.
export function buildSequence(
  page: Pick<ListSessionsResponse, 'items'>,
  openRuns: readonly string[],
  runPage: (first: SequenceRow, page: number) => readonly SequenceRow[] | undefined,
  perPage: number,
): SequenceRow[] {
  const out: SequenceRow[] = []
  for (const row of page.items) {
    out.push(row)
    if (!row.run || !openRuns.includes(row.id)) continue
    const pages = Math.ceil(row.run.count / perPage)
    for (let p = 1; p <= pages; p++) {
      const items = runPage(row, p)
      if (!items) break
      out.push(...items)
    }
  }
  return out
}
