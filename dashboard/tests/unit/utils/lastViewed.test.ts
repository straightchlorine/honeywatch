import { afterEach, describe, expect, it } from 'vitest'
import { setLastViewed, setViewedSpot, takeLastViewed, takeViewedSpot } from '@/utils/lastViewed'

describe('lastViewed', () => {
  afterEach(() => {
    takeLastViewed()
    takeViewedSpot()
  })

  it('hands the id out once, then clears it', () => {
    setLastViewed('a1b2')
    expect(takeLastViewed()).toBe('a1b2')
    expect(takeLastViewed()).toBeNull()
  })

  it('keeps only the latest id', () => {
    setLastViewed('first')
    setLastViewed('second')
    expect(takeLastViewed()).toBe('second')
  })

  it('treats an empty id as no id', () => {
    setLastViewed('')
    expect(takeLastViewed()).toBeNull()
  })

  it('hands the viewed spot out once', () => {
    const spot = { id: 'a1b2', top: 120, runs: new Map([['r', 2]]) }
    setViewedSpot(spot)
    expect(takeViewedSpot()).toBe(spot)
    expect(takeViewedSpot()).toBeNull()
  })
})
