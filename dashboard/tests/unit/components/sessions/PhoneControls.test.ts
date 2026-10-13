import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import PhoneControls from '@/components/sessions/PhoneControls.vue'

const SORTS = [
  { value: 'interest', label: 'Most interesting', short: 'Interesting', hint: 'ranked' },
  { value: 'recent', label: 'Most recent', short: 'Newest' },
]
const COUNTRIES = [
  { value: '', label: 'All countries' },
  { value: 'BG', label: 'Bulgaria', icon: 'x' },
]
const COUNTS = { shell: 5, commands: 4, tcpip: 3, downloads: 2, none: 1, total: 15 }

function mountPc(props: Record<string, unknown> = {}) {
  return mount(PhoneControls, {
    props: {
      has: '',
      sort: 'interest',
      country: '',
      sortOptions: SORTS,
      countryOptions: COUNTRIES,
      counts: COUNTS,
      ...props,
    },
    attachTo: document.body,
  })
}
const sheet = () => document.querySelector('[role="dialog"]')
const pills = (w: ReturnType<typeof mountPc>) => w.findAll('button.pc-pill')

describe('PhoneControls', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows the short sort name and the unset category names on the pills', () => {
    const w = mountPc()
    expect(pills(w).map((p) => p.text())).toEqual(['Outcome', 'Interesting', 'Country'])
    expect(pills(w)[1]!.attributes('aria-label')).toBe('Sort: Most interesting')
    w.unmount()
  })

  it('opens a labelled modal dialog from a pill and picks a sort', async () => {
    const w = mountPc()
    await pills(w)[1]!.trigger('click')
    expect(sheet()?.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(sheet()!.getAttribute('aria-labelledby')!)?.textContent).toBe(
      'Sort sessions',
    )
    const radios = [...document.querySelectorAll<HTMLElement>('[role="radio"]')]
    expect(radios.map((r) => r.getAttribute('aria-checked'))).toEqual(['true', 'false'])
    radios[1]!.click()
    await w.vm.$nextTick()
    expect(w.emitted('update:sort')).toEqual([['recent']])
    expect(sheet()).toBeNull()
    w.unmount()
  })

  it('leads every outcome row with an icon', async () => {
    const w = mountPc()
    await pills(w)[0]!.trigger('click')
    const rows = [...document.querySelectorAll('.pc-opt')]
    expect(rows).toHaveLength(5)
    for (const r of rows) expect(r.querySelector('svg.pc-oi path')?.getAttribute('d')).toBeTruthy()
  })

  it('picks a country', async () => {
    const w = mountPc()
    await pills(w)[2]!.trigger('click')
    document.querySelectorAll<HTMLElement>('[role="radio"]')[1]!.click()
    expect(w.emitted('update:country')).toEqual([['BG']])
    w.unmount()
  })

  it('outcome rows toggle has= tokens and stay open until Done', async () => {
    const w = mountPc({ has: 'success' })
    expect(pills(w)[0]!.text()).toBe('Control')
    await pills(w)[0]!.trigger('click')
    const boxes = [...document.querySelectorAll<HTMLElement>('[role="checkbox"]')]
    expect(boxes[0]!.getAttribute('aria-checked')).toBe('true')
    boxes[1]!.click()
    expect(w.emitted('update:has')).toEqual([['success,commands']])
    expect(sheet()).not.toBeNull()
    boxes[4]!.click()
    expect(w.emitted('update:has')?.[1]).toEqual(['none'])
    ;(document.querySelector('.pc-done') as HTMLElement).click()
    await w.vm.$nextTick()
    expect(sheet()).toBeNull()
    w.unmount()
  })

  it('Escape closes the sheet and returns focus to the opening pill', async () => {
    const w = mountPc()
    await pills(w)[1]!.trigger('click')
    await w.vm.$nextTick()
    expect(document.activeElement).toBe(
      document.querySelector('[role="radio"][aria-checked="true"]'),
    )
    sheet()!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(sheet()).toBeNull()
    expect(document.activeElement).toBe(pills(w)[1]!.element)
    w.unmount()
  })

  it('Clear keeps focus in the sheet so Escape still closes it', async () => {
    const w = mountPc({ has: 'success' })
    await pills(w)[0]!.trigger('click')
    await w.vm.$nextTick()
    ;(document.querySelector('.pc-clear') as HTMLElement).click()
    expect(document.activeElement).toBe(document.querySelector('.pc-done'))
    w.unmount()
  })

  it('traps Tab inside the sheet', async () => {
    const w = mountPc()
    await pills(w)[1]!.trigger('click')
    await w.vm.$nextTick()
    const radios = document.querySelectorAll<HTMLElement>('[role="radio"]')
    radios[radios.length - 1]!.focus()
    const ev = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
    radios[radios.length - 1]!.dispatchEvent(ev)
    expect(ev.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(radios[0])
    w.unmount()
  })

  it('a scrim tap closes the sheet', async () => {
    const w = mountPc()
    await pills(w)[2]!.trigger('click')
    ;(document.querySelector('.pc-scrim') as HTMLElement).click()
    await w.vm.$nextTick()
    expect(sheet()).toBeNull()
    w.unmount()
  })
})
