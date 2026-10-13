import { describe, expect, it } from 'vitest'
import type { SessionSummaryResponse } from '@/api/generated/types.gen'
import { buildSequence } from '@/utils/sessionSequence'

const row = (id: string, count = 0) =>
  ({ id, run: count ? { count, offset: 0 } : null }) as unknown as SessionSummaryResponse
const ids = (rows: SessionSummaryResponse[]) => rows.map((r) => r.id)

describe('buildSequence', () => {
  const page = { items: [row('a'), row('b', 3), row('c', 2), row('d')] }
  const members: Record<string, Record<number, SessionSummaryResponse[]>> = {
    b: { 1: [row('b1'), row('b2')], 2: [row('b3')] },
    c: { 1: [row('c1'), row('c2')] },
  }
  const runPage = (first: SessionSummaryResponse, n: number) => members[first.id]?.[n]

  it('is the list order when no run is open', () => {
    expect(ids(buildSequence(page, [''], runPage, 2))).toEqual(['a', 'b', 'c', 'd'])
  })

  it('puts an open run members right after its first session, across pages', () => {
    expect(ids(buildSequence(page, ['b'], runPage, 2))).toEqual([
      'a',
      'b',
      'b1',
      'b2',
      'b3',
      'c',
      'd',
    ])
  })

  it('handles two open runs', () => {
    expect(ids(buildSequence(page, ['b', 'c'], runPage, 2))).toEqual([
      'a',
      'b',
      'b1',
      'b2',
      'b3',
      'c',
      'c1',
      'c2',
      'd',
    ])
  })

  it('skips members of a run named but not cached', () => {
    expect(ids(buildSequence(page, ['c'], () => undefined, 2))).toEqual(['a', 'b', 'c', 'd'])
  })

  it('stops a run at the first uncached page', () => {
    const only1 = (first: SessionSummaryResponse, n: number) =>
      n === 1 ? runPage(first, 1) : undefined
    expect(ids(buildSequence(page, ['b'], only1, 2))).toEqual(['a', 'b', 'b1', 'b2', 'c', 'd'])
  })
})
