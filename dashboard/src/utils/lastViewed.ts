// The session last opened from the list, so Back can return focus to its row.
let id: string | null = null

export function setLastViewed(next: string | null): void {
  id = next || null
}

export function takeLastViewed(): string | null {
  const taken = id
  id = null
  return taken
}

// Where the tapped row sat and how deep each run was open, so Back can put it back on the same
// screen line even when the rows above it were loaded by "Show more".
export interface ViewedSpot {
  id: string
  top: number
  runs: Map<string, number>
}
let spot: ViewedSpot | null = null

export function setViewedSpot(next: ViewedSpot): void {
  spot = next
}

export function takeViewedSpot(): ViewedSpot | null {
  const taken = spot
  spot = null
  return taken
}
