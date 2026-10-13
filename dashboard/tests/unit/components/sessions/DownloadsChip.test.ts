import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DownloadsChip from '@/components/sessions/DownloadsChip.vue'

const dl = (id: number, sha256: string | null) => ({ id, sha256, timestamp: null, url: null })
const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)

function chip(downloads: ReturnType<typeof dl>[]) {
  return mount(DownloadsChip, {
    props: { downloads, label: String(downloads.length), title: 'files' },
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' },
      },
    },
  })
}

describe('DownloadsChip', () => {
  it('links one kept file straight to its payloads specimen', () => {
    const w = chip([dl(1, SHA_A)])
    expect(w.find('button').exists()).toBe(false)
    expect(JSON.parse(w.find('a').attributes('data-to')!)).toEqual({
      name: 'payloads',
      hash: `#spec-${SHA_A}`,
    })
  })

  it('treats a repeated sha as one file', () => {
    expect(
      chip([dl(1, SHA_A), dl(2, SHA_A)])
        .find('button')
        .exists(),
    ).toBe(false)
  })

  it('opens a list of short digests for several files and closes on Escape', async () => {
    const w = chip([dl(1, SHA_A), dl(2, SHA_B)])
    const btn = w.find('button')
    expect(btn.attributes('aria-expanded')).toBe('false')
    await btn.trigger('click')
    expect(btn.attributes('aria-expanded')).toBe('true')
    const items = w.findAll('.dl-item')
    expect(items.map((i) => i.find('.dl-sha').text())).toEqual(['a'.repeat(12), 'b'.repeat(12)])
    await w.find('.dl-list').trigger('keydown', { key: 'Escape' })
    expect(w.find('.dl-list').exists()).toBe(false)
  })

  it('shows an uncaptured download as not kept, with no link', async () => {
    const w = chip([dl(1, null)])
    await w.find('button').trigger('click')
    expect(w.find('.dl-item').exists()).toBe(false)
    expect(w.find('.dl-none').text()).toBe('not kept')
  })

  it('puts the disclosure arrow after the file glyph', () => {
    const w = chip([dl(1, SHA_A), dl(2, SHA_B)])
    const kids = [...w.find('button .chip').element.children].map((e) => e.getAttribute('class'))
    expect(kids).toEqual(['', 'chip-icon', 'caret'])
  })

  it('offers VirusTotal per kept file and marks repeats and not-kept rows', async () => {
    const w = chip([dl(1, SHA_A), dl(2, SHA_A), dl(3, SHA_B), dl(4, null), dl(5, null)])
    await w.find('button').trigger('click')
    expect(w.findAll('.dl-vt').map((a) => a.attributes('href'))).toEqual([
      `https://www.virustotal.com/gui/file/${SHA_A}`,
      `https://www.virustotal.com/gui/file/${SHA_B}`,
    ])
    expect(w.find('.dl-n').text()).toBe('\u00d72')
    expect(w.find('.dl-none').text()).toContain('not kept')
    expect(w.find('.dl-none .dl-n').text()).toBe('\u00d72')
  })
})
