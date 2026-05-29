import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IconLink from '@/components/IconLink.vue'

describe('IconLink', () => {
  it('renders an allowed https href with label and safe rel/target', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const a = w.get('a')
    expect(a.attributes('href')).toBe('https://example.com')
    expect(a.attributes('aria-label')).toBe('GitHub')
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toContain('noopener')
  })

  it('allows root-relative and hash hrefs', () => {
    expect(
      mount(IconLink, { props: { icon: 'github', href: '/x', label: 'a' } })
        .get('a')
        .attributes('href'),
    ).toBe('/x')
    expect(
      mount(IconLink, { props: { icon: 'github', href: '#y', label: 'a' } })
        .get('a')
        .attributes('href'),
    ).toBe('#y')
  })

  it('blocks disallowed schemes by collapsing to "#"', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'javascript:alert(1)', label: 'a' },
    })
    expect(w.get('a').attributes('href')).toBe('#')
  })
})
