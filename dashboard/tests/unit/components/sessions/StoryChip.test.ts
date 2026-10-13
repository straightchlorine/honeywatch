import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StoryChip from '@/components/sessions/StoryChip.vue'

const chip = (props: Record<string, unknown>) =>
  mount(StoryChip, { props, slots: { default: '3 commands' } })

describe('StoryChip accessible name', () => {
  it('becomes an image when the caller names it, even without a glyph', () => {
    const w = mount(StoryChip, {
      props: { icon: 'key' },
      attrs: { 'aria-label': '3 commands typed' },
      slots: { default: '3' },
    })
    expect(w.attributes('role')).toBe('img')
    expect(w.attributes('aria-label')).toBe('3 commands typed')
  })

  it('stays plain text with no name, so links keep their text', () => {
    expect(chip({}).attributes('role')).toBeUndefined()
  })
})

describe('StoryChip iconOnly', () => {
  it('marks the glyph-only mode so the words are hidden at any width', () => {
    const w = chip({ glyph: 'key', iconOnly: true })
    expect(w.classes()).toContain('only')
    expect(w.attributes('role')).toBe('img')
    expect(w.find('.word').exists()).toBe(true)
  })

  it('stays width-driven without iconOnly', () => {
    const w = chip({ glyph: 'key' })
    expect(w.classes()).not.toContain('only')
    expect(w.classes()).toContain('glyphed')
  })

  it('ignores iconOnly when there is no glyph', () => {
    expect(chip({ iconOnly: true }).classes()).not.toContain('only')
  })
})
