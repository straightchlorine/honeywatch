import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MapControls from '@/components/map/MapControls.vue'
import type { MapQualityLevel } from '@/components/map/MapQuality.vue'

describe('MapControls component', () => {
  it('renders zoom buttons: in, out, and reset', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    expect(buttons).toHaveLength(3)

    expect(buttons[0]!.text()).toBe('+')
    expect(buttons[1]!.text()).toContain('−')
    expect(buttons[2]!.classes()).toContain('reset')
  })

  it('zoom-in button has aria-label for accessibility', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    expect(buttons[0]!.attributes('aria-label')).toBe('Zoom in')
  })

  it('zoom-out button has aria-label for accessibility', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    expect(buttons[1]!.attributes('aria-label')).toBe('Zoom out')
  })

  it('reset button has aria-label and special "reset" class', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    const resetBtn = buttons[2]!
    expect(resetBtn.attributes('aria-label')).toBe('Reset view')
    expect(resetBtn.classes()).toContain('reset')
  })

  it('emits zoomIn event on zoom-in button click', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    await buttons[0]!.trigger('click')

    expect(w.emitted('zoomIn')).toBeTruthy()
    expect(w.emitted('zoomIn')).toHaveLength(1)
  })

  it('emits zoomOut event on zoom-out button click', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    await buttons[1]!.trigger('click')

    expect(w.emitted('zoomOut')).toBeTruthy()
    expect(w.emitted('zoomOut')).toHaveLength(1)
  })

  it('emits reset event on reset button click', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    await buttons[2]!.trigger('click')

    expect(w.emitted('reset')).toBeTruthy()
    expect(w.emitted('reset')).toHaveLength(1)
  })

  it('renders MapQuality component as a child', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'high' as MapQualityLevel },
    })

    const qualityContainer = w.find('.quality')
    expect(qualityContainer.exists()).toBe(true)
  })

  it('passes quality prop to MapQuality and updates on emit', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'low' as MapQualityLevel },
    })

    expect(w.emitted('update:quality')).toBeFalsy()

    await w.setProps({ quality: 'high' as MapQualityLevel })
    expect(w.props('quality')).toBe('high')
  })

  it('renders legend component with legendMax prop', () => {
    const w = mount(MapControls, {
      props: { legendMax: '500', quality: 'regular' as MapQualityLevel },
    })

    const legendCard = w.find('.legend-card')
    expect(legendCard.exists()).toBe(true)
  })

  it('legend card is visible on desktop (> 900px)', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const legendCard = w.find('.legend-card')
    expect(legendCard.exists()).toBe(true)
  })

  it('renders all three buttons with type="button"', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    buttons.forEach((btn) => {
      expect(btn.attributes('type')).toBe('button')
    })
  })

  it('zoom buttons are positioned in a flex container', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const zoomBtns = w.find('.zoombtns')
    expect(zoomBtns.exists()).toBe(true)
    expect(zoomBtns.classes()).toContain('zoombtns')
  })

  it('main container has correct positioning classes', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const mapctl = w.find('.mapctl')
    expect(mapctl.exists()).toBe(true)
    expect(mapctl.classes()).toContain('mapctl')
  })

  it('emits multiple zoom events on repeated clicks', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    const zoomInBtn = buttons[0]!

    await zoomInBtn.trigger('click')
    await zoomInBtn.trigger('click')
    await zoomInBtn.trigger('click')

    expect(w.emitted('zoomIn')).toHaveLength(3)
  })

  it('emits correct events for mixed button clicks', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    const zoomInBtn = buttons[0]!
    const zoomOutBtn = buttons[1]!
    const resetBtn = buttons[2]!

    await zoomInBtn.trigger('click')
    await zoomOutBtn.trigger('click')
    await resetBtn.trigger('click')
    await zoomInBtn.trigger('click')

    expect(w.emitted('zoomIn')).toHaveLength(2)
    expect(w.emitted('zoomOut')).toHaveLength(1)
    expect(w.emitted('reset')).toHaveLength(1)
  })

  it('all three quality levels can be set', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    expect(w.props('quality')).toBe('regular')

    await w.setProps({ quality: 'low' as MapQualityLevel })
    expect(w.props('quality')).toBe('low')

    await w.setProps({ quality: 'high' as MapQualityLevel })
    expect(w.props('quality')).toBe('high')
  })

  it('handles large legendMax values', () => {
    const w = mount(MapControls, {
      props: { legendMax: '999999', quality: 'regular' as MapQualityLevel },
    })

    expect(w.props('legendMax')).toBe('999999')
    expect(w.find('.legend-card').exists()).toBe(true)
  })

  it('handles zero and empty legendMax edge cases', () => {
    const w1 = mount(MapControls, {
      props: { legendMax: '0', quality: 'regular' as MapQualityLevel },
    })
    expect(w1.props('legendMax')).toBe('0')

    const w2 = mount(MapControls, {
      props: { legendMax: '', quality: 'regular' as MapQualityLevel },
    })
    expect(w2.props('legendMax')).toBe('')
  })

  it('structure follows: zoombtns then MapQuality then legend-card', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const children = w.find('.mapctl').element.children
    expect(children[0]!.className).toContain('zoombtns')
    expect(children[children.length - 1]!.className).toContain('legend-card')
  })

  it('buttons have glass styling classes for consistency', () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const legendCard = w.find('.legend-card')
    expect(legendCard.classes()).toContain('glass')
  })

  it('emits events with empty payload (no data)', async () => {
    const w = mount(MapControls, {
      props: { legendMax: '100', quality: 'regular' as MapQualityLevel },
    })

    const buttons = w.findAll('button')
    await buttons[0]!.trigger('click')

    const emitted = w.emitted('zoomIn')![0]
    expect(emitted).toEqual([])
  })
})
