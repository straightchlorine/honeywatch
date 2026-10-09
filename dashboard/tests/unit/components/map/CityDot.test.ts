import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CityDot from '@/components/map/CityDot.vue'
import type { MapCityResponse } from '@/api/generated/types.gen'

function createCity(overrides: Partial<MapCityResponse> = {}): MapCityResponse {
  return {
    city: 'Test City',
    country_code: 'TC',
    ...overrides,
  } as MapCityResponse
}

describe('CityDot component', () => {
  it('renders a group with visible and hit circles', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const circles = w.findAll('circle')
    expect(circles).toHaveLength(2)
    expect(circles[0]!.classes()).toContain('city-hit')
    expect(circles[1]!.classes()).toContain('city-dot')
  })

  it('positions the group at the specified x, y coordinates', () => {
    const w = mount(CityDot, {
      props: {
        x: 500,
        y: 300,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const g = w.get('g')
    expect(g.attributes('transform')).toBe('translate(500,300)')
  })

  it('scales the visible dot radius by the scale factor', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 2,
      },
    })

    const dots = w.findAll('circle')
    const visibleDot = dots[1]!
    expect(visibleDot.attributes('r')).toBe('10')
  })

  it('sets hit circle radius to (r + 3) * scale when greater than minHitR', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    expect(hitCircle.attributes('r')).toBe('8')
  })

  it('respects minHitR prop to enforce minimum hit circle size', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 1,
        city: createCity(),
        scale: 1,
        minHitR: 12,
      },
    })

    const hitCircle = w.get('.city-hit')
    expect(Number(hitCircle.attributes('r'))).toBe(12)
  })

  it('hit circle grows proportionally when scale increases', async () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    let hitCircle = w.get('.city-hit')
    const r1 = Number(hitCircle.attributes('r'))

    await w.setProps({ scale: 2 })
    hitCircle = w.get('.city-hit')
    const r2 = Number(hitCircle.attributes('r'))

    expect(r2).toBe(r1 * 2)
  })

  it('hides the pointer-only hit circle from assistive tech and the tab order', () => {
    const city = createCity({ city: 'New York', country_code: 'US' })
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    expect(hitCircle.attributes('aria-hidden')).toBe('true')
    expect(hitCircle.attributes('role')).toBeUndefined()
    expect(hitCircle.attributes('tabindex')).toBeUndefined()
  })

  it('emits select with country_code on click', async () => {
    const city = createCity({ country_code: 'FR' })
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    await w.get('.city-hit').trigger('click')

    expect(w.emitted('select')).toBeTruthy()
    expect(w.emitted('select')![0]![0]).toBe('FR')
  })

  it('does not emit select on click if country_code is empty', async () => {
    const city = createCity({ country_code: '' })
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    await w.get('.city-hit').trigger('click')

    expect(w.emitted('select')).toBeFalsy()
  })

  it('emits tooltip-enter with city and event on pointerenter for non-touch', async () => {
    const city = createCity({ city: 'Berlin', country_code: 'DE' })
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    await hitCircle.trigger('pointerenter', { pointerType: 'mouse' })

    expect(w.emitted('tooltip-enter')).toBeTruthy()
    expect(w.emitted('tooltip-enter')![0]![0]).toEqual(city)
    expect(w.emitted('tooltip-enter')![0]![1]).toBeTruthy()
  })

  it('does not emit tooltip-enter on pointerenter for touch events', async () => {
    const city = createCity()
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    await hitCircle.trigger('pointerenter', { pointerType: 'touch' })

    expect(w.emitted('tooltip-enter')).toBeFalsy()
  })

  it('emits tooltip-move on pointermove', async () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    await hitCircle.trigger('pointermove')

    expect(w.emitted('tooltip-move')).toBeTruthy()
    expect(w.emitted('tooltip-move')![0]![0]).toBeTruthy()
  })

  it('emits tooltip-leave on pointerleave', async () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')
    await hitCircle.trigger('pointerleave')

    expect(w.emitted('tooltip-leave')).toBeTruthy()
  })

  it('visible dot has correct fill color', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 1,
      },
    })

    const visibleDot = w.get('.city-dot')
    expect(visibleDot.attributes('fill')).toBe('#f3e5c4')
  })

  it('handles large scale values correctly', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 10,
      },
    })

    const visibleDot = w.get('.city-dot')
    const hitCircle = w.get('.city-hit')

    expect(visibleDot.attributes('r')).toBe('50')
    expect(hitCircle.attributes('r')).toBe('80')
  })

  it('handles fractional scale values', () => {
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city: createCity(),
        scale: 0.5,
      },
    })

    const visibleDot = w.get('.city-dot')
    const hitCircle = w.get('.city-hit')

    expect(visibleDot.attributes('r')).toBe('2.5')
    expect(hitCircle.attributes('r')).toBe('4')
  })

  it('emits all events in correct sequence for full interaction', async () => {
    const city = createCity({ country_code: 'CH' })
    const w = mount(CityDot, {
      props: {
        x: 100,
        y: 200,
        r: 5,
        city,
        scale: 1,
      },
    })

    const hitCircle = w.get('.city-hit')

    await hitCircle.trigger('pointerenter', { pointerType: 'mouse' })
    await hitCircle.trigger('pointermove')
    await hitCircle.trigger('pointerleave')

    expect(w.emitted('tooltip-enter')).toBeTruthy()
    expect(w.emitted('tooltip-move')).toBeTruthy()
    expect(w.emitted('tooltip-leave')).toBeTruthy()

    expect(w.emitted('select')).toBeFalsy()
  })
})
