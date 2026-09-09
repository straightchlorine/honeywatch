import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MapQuality, { type MapQualityLevel } from '@/components/map/MapQuality.vue'

describe('MapQuality component', () => {
  it('renders a range input slider with correct configuration', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const input = w.get('input[type="range"]')
    expect(input.attributes('min')).toBe('0')
    expect(input.attributes('max')).toBe('2')
    expect(input.attributes('step')).toBe('1')
    expect(input.attributes('aria-label')).toBe('Map detail')
  })

  it('renders all three level options in datalist', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const options = w.findAll('datalist option')
    expect(options).toHaveLength(3)
    expect(options[0]!.attributes('value')).toBe('0')
    expect(options[0]!.attributes('label')).toBe('Low')
    expect(options[1]!.attributes('value')).toBe('1')
    expect(options[1]!.attributes('label')).toBe('Regular')
    expect(options[2]!.attributes('value')).toBe('2')
    expect(options[2]!.attributes('label')).toBe('High')
  })

  it('displays the current quality level text ("Low", "Regular", or "High")', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'high' },
    })

    const valueDisplay = w.get('.val')
    expect(valueDisplay.text()).toBe('High')
  })

  it('updates display text when model changes from low to high', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    expect(w.get('.val').text()).toBe('Low')
    await w.setProps({ modelValue: 'high' })
    expect(w.get('.val').text()).toBe('High')
  })

  it('emits update:modelValue when slider changes to 0 (low)', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const input = w.get('input[type="range"]')
    await input.setValue(0)

    expect(w.emitted('update:modelValue')).toBeTruthy()
    expect(w.emitted('update:modelValue')![0]![0]).toBe('low')
  })

  it('emits update:modelValue when slider changes to 1 (regular)', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    const input = w.get('input[type="range"]')
    await input.setValue(1)

    expect(w.emitted('update:modelValue')![0]![0]).toBe('regular')
  })

  it('emits update:modelValue when slider changes to 2 (high)', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    const input = w.get('input[type="range"]')
    await input.setValue(2)

    expect(w.emitted('update:modelValue')![0]![0]).toBe('high')
  })

  it('clamps slider values at boundaries: 0 and 2', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const input = w.get('input[type="range"]')
    await input.setValue(0)
    expect(w.emitted('update:modelValue')![0]![0]).toBe('low')

    await w.setProps({ modelValue: 'low' })
    await input.setValue(2)
    expect(w.emitted('update:modelValue')).toBeTruthy()
    const emissions = w.emitted('update:modelValue')!
    expect(emissions[emissions.length - 1]![0]).toBe('high')
  })

  it('sets correct aria-valuetext attribute for accessibility', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    let input = w.get('input[type="range"]')
    expect(input.attributes('aria-valuetext')).toBe('Low')

    await w.setProps({ modelValue: 'regular' })
    input = w.get('input[type="range"]')
    expect(input.attributes('aria-valuetext')).toBe('Regular')

    await w.setProps({ modelValue: 'high' })
    input = w.get('input[type="range"]')
    expect(input.attributes('aria-valuetext')).toBe('High')
  })

  it('has decorative "Map detail" caption with aria-hidden', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const cap = w.get('.cap')
    expect(cap.text()).toBe('Map detail')
    expect(cap.attributes('aria-hidden')).toBe('true')
  })

  it('renders in a glass container with appropriate classes', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const container = w.get('.quality')
    expect(container.classes()).toContain('glass')
  })

  it('has datalist id matching the input list attribute', () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' },
    })

    const input = w.get('input[type="range"]')
    const datalistId = input.attributes('list')
    const datalist = w.find(`datalist#${datalistId}`)

    expect(datalist.exists()).toBe(true)
    expect(datalistId).toBe('map-quality-stops')
  })

  it('handles all three levels in sequence: low -> regular -> high', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    const input = w.get('input[type="range"]')

    expect(w.get('.val').text()).toBe('Low')

    await input.setValue(1)
    await w.setProps({ modelValue: 'regular' })
    expect(w.get('.val').text()).toBe('Regular')

    await input.setValue(2)
    await w.setProps({ modelValue: 'high' })
    expect(w.get('.val').text()).toBe('High')

    await input.setValue(1)
    await w.setProps({ modelValue: 'regular' })
    expect(w.get('.val').text()).toBe('Regular')
  })

  it('preserves model type (MapQualityLevel) through updates', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'regular' as MapQualityLevel },
    })

    const input = w.get('input[type="range"]')
    await input.setValue(0)

    const emitted = w.emitted('update:modelValue')![0]![0]
    expect(['low', 'regular', 'high']).toContain(emitted)
  })

  it('slider value reflects current model index correctly', async () => {
    const w = mount(MapQuality, {
      props: { modelValue: 'low' },
    })

    let input = w.get('input[type="range"]')
    expect((input.element as HTMLInputElement).value).toBe('0')

    await w.setProps({ modelValue: 'regular' })
    input = w.get('input[type="range"]')
    expect((input.element as HTMLInputElement).value).toBe('1')

    await w.setProps({ modelValue: 'high' })
    input = w.get('input[type="range"]')
    expect((input.element as HTMLInputElement).value).toBe('2')
  })
})
