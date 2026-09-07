import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OutcomeFilter from '@/components/sessions/OutcomeFilter.vue'
import type { OutcomeCountsResponse } from '@/api/generated/types.gen'

const COUNTS: OutcomeCountsResponse = {
  shell: 18742,
  commands: 9731,
  tcpip: 8100,
  downloads: 156,
  none: 524263,
  total: 543006,
}

function mountOf(modelValue = '', counts: OutcomeCountsResponse | null = COUNTS) {
  return mount(OutcomeFilter, { props: { modelValue, counts }, attachTo: document.body })
}

function checkboxFor(w: ReturnType<typeof mountOf>, label: string) {
  const row = w.findAll('.of-row').find((r) => r.text().includes(label))
  return row!.find('input[type="checkbox"]')
}

describe('OutcomeFilter', () => {
  it('opens the panel on trigger click and closes on a second click', async () => {
    const w = mountOf()
    expect(w.find('.of-panel').exists()).toBe(false)
    await w.find('.of-trigger').trigger('click')
    expect(w.find('.of-panel').exists()).toBe(true)
    expect(w.find('.of-trigger').attributes('aria-expanded')).toBe('true')
    await w.find('.of-trigger').trigger('click')
    expect(w.find('.of-panel').exists()).toBe(false)
    w.unmount()
  })

  it('Escape closes the panel and returns focus to the trigger', async () => {
    const w = mountOf()
    await w.find('.of-trigger').trigger('click')
    expect(w.find('.of-panel').exists()).toBe(true)
    await w.find('.of-panel').trigger('keydown', { key: 'Escape' })
    expect(w.find('.of-panel').exists()).toBe(false)
    expect(document.activeElement).toBe(w.find('.of-trigger').element)
    w.unmount()
  })

  it('ticking one box emits the matching has= token', async () => {
    const w = mountOf()
    await w.find('.of-trigger').trigger('click')
    await checkboxFor(w, 'Got control').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['success'])
    w.unmount()
  })

  it('ticking two boxes emits a comma list in canonical row order', async () => {
    // Controlled component: each toggle only sees modelValue after parent's v-model round-trip
    const w = mountOf()
    await w.find('.of-trigger').trigger('click')
    await checkboxFor(w, 'Ran commands').setValue(true)
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['commands'])
    await w.setProps({ modelValue: 'commands' })
    await checkboxFor(w, 'Got control').setValue(true)
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['success,commands'])
    w.unmount()
  })

  it('ticking "Nothing at all" clears every other selection', async () => {
    const w = mountOf('commands,success')
    await w.find('.of-trigger').trigger('click')
    await checkboxFor(w, 'Nothing at all').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['none'])
    w.unmount()
  })

  it('ticking any other box clears "Nothing at all"', async () => {
    const w = mountOf('none')
    await w.find('.of-trigger').trigger('click')
    await checkboxFor(w, 'Dropped a file').setValue(true)
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['downloads'])
    w.unmount()
  })

  it('never emits "none" alongside another token, no matter the click order', async () => {
    const w = mountOf()
    await w.find('.of-trigger').trigger('click')
    async function tickAndSync(label: string): Promise<void> {
      await checkboxFor(w, label).setValue(true)
      const value = w.emitted('update:modelValue')?.at(-1)?.[0]
      await w.setProps({ modelValue: value as string })
    }
    await tickAndSync('Tried to relay')
    await tickAndSync('Nothing at all')
    await tickAndSync('Ran commands')
    for (const [value] of w.emitted('update:modelValue') ?? []) {
      const tokens = String(value).split(',')
      expect(tokens.includes('none') && tokens.length > 1).toBe(false)
    }
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['commands'])
    w.unmount()
  })

  it('renders counts via fmtNumber, with the "none" count in the bad tone', async () => {
    const w = mountOf()
    await w.find('.of-trigger').trigger('click')
    const noneRow = w.findAll('.of-row').find((r) => r.text().includes('Nothing at all'))
    expect(noneRow!.text()).toContain('524,263')
    expect(noneRow!.find('.of-count-bad').exists()).toBe(true)
    w.unmount()
  })

  it('shows a dash, not a zero, while counts is null', async () => {
    const w = mountOf('', null)
    await w.find('.of-trigger').trigger('click')
    const shellRow = w.findAll('.of-row').find((r) => r.text().includes('Got control'))
    expect(shellRow!.find('.of-row-count').text()).toBe('-')
    w.unmount()
  })

  it('trigger label names the single selection, and counts multi-select', async () => {
    expect(mountOf('success').find('.of-trigger-label').text()).toBe('Outcome: Got control')
    expect(mountOf('success,commands').find('.of-trigger-label').text()).toBe(
      'Outcome: 2 selected',
    )
    expect(mountOf().find('.of-trigger-label').text()).toBe('Outcome')
  })

  it('shows a clear button only when a selection is active, and clearing emits empty string', async () => {
    const empty = mountOf()
    expect(empty.find('.of-clear').exists()).toBe(false)

    const w = mountOf('success')
    expect(w.find('.of-clear').exists()).toBe(true)
    await w.find('.of-clear').trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([''])
  })
})
