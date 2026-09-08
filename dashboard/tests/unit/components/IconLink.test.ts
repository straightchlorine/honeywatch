import { mount } from '@vue/test-utils'
import { describe, expect, it, vi, afterEach } from 'vitest'
import IconLink from '@/components/IconLink.vue'

describe('IconLink', () => {
  afterEach(() => {
    // Keep tooltip DOM element; singleton composable reuses it across tests.
    const el = document.querySelector('.hw-tooltip')
    if (el) {
      el.classList.remove('show')
      el.replaceChildren()
      el.removeAttribute('style')
    }
    vi.clearAllMocks()
  })

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

  it('renders the icon SVG with correct viewBox and aria-hidden', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const svg = w.find('svg')
    expect(svg.exists()).toBe(true)
    expect(svg.attributes('viewBox')).toBe('0 0 24 24')
    expect(svg.attributes('aria-hidden')).toBe('true')
    expect(svg.attributes('focusable')).toBe('false')
  })

  it('renders the SVG path with the correct icon data', () => {
    const w = mount(IconLink, {
      props: {
        icon: 'check',
        href: 'https://example.com',
        label: 'Done',
      },
    })
    const path = w.find('svg path')
    expect(path.exists()).toBe(true)
    const pathD = path.attributes('d')
    expect(pathD).toBeTruthy()
    expect(pathD?.length).toBeGreaterThan(0)
  })

  it('supports different icon types (linkedin, codeberg, etc)', () => {
    const icons: Array<'github' | 'linkedin' | 'codeberg'> = ['github', 'linkedin', 'codeberg']
    icons.forEach((icon) => {
      const w = mount(IconLink, {
        props: { icon, href: 'https://example.com', label: icon },
      })
      const path = w.find('svg path')
      expect(path.exists()).toBe(true)
      expect(path.attributes('d')).toBeTruthy()
    })
  })

  it('shows tooltip on pointerenter event', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const link = w.get('a')
    await link.trigger('pointerenter')

    const tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip).toBeTruthy()
    expect(tooltip?.classList.contains('show')).toBe(true)
    expect(tooltip?.textContent).toContain('GitHub')
  })

  it('calls move on pointermove event', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const link = w.get('a')
    await link.trigger('pointerenter')

    const tooltip = document.querySelector('.hw-tooltip') as HTMLDivElement
    expect(tooltip).toBeTruthy()
    expect(tooltip.classList.contains('show')).toBe(true)

    // Positioning logic tested in useHwTooltip tests.
    await link.trigger('pointermove')
    expect(tooltip.classList.contains('show')).toBe(true)
  })

  it('hides tooltip on pointerleave event', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const link = w.get('a')
    await link.trigger('pointerenter')

    let tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.classList.contains('show')).toBe(true)

    await link.trigger('pointerleave')
    tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.classList.contains('show')).toBe(false)
  })

  it('shows tooltip on focus event', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const link = w.get('a')
    await link.trigger('focus')

    const tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip).toBeTruthy()
    expect(tooltip?.classList.contains('show')).toBe(true)
    expect(tooltip?.textContent).toContain('GitHub')
  })

  it('hides tooltip on blur event', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const link = w.get('a')
    await link.trigger('focus')

    let tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.classList.contains('show')).toBe(true)

    await link.trigger('blur')
    tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.classList.contains('show')).toBe(false)
  })

  it('passes correct label to tooltip on both pointer and focus events', async () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'My GitHub Profile' },
    })
    const link = w.get('a')

    await link.trigger('pointerenter')
    let tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.textContent).toContain('My GitHub Profile')

    await link.trigger('pointerleave')

    await link.trigger('focus')
    tooltip = document.querySelector('.hw-tooltip')
    expect(tooltip?.textContent).toContain('My GitHub Profile')
  })

  it('blocks data: scheme in href', () => {
    const w = mount(IconLink, {
      props: {
        icon: 'github',
        href: 'data:text/html,<script>alert(1)</script>',
        label: 'a',
      },
    })
    expect(w.get('a').attributes('href')).toBe('#')
  })

  it('blocks file: scheme in href', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'file:///etc/passwd', label: 'a' },
    })
    expect(w.get('a').attributes('href')).toBe('#')
  })

  it('allows http and https schemes (case-insensitive)', () => {
    expect(
      mount(IconLink, {
        props: { icon: 'github', href: 'HTTP://example.com', label: 'a' },
      })
        .get('a')
        .attributes('href'),
    ).toBe('HTTP://example.com')
    expect(
      mount(IconLink, {
        props: { icon: 'github', href: 'HTTPS://example.com', label: 'a' },
      })
        .get('a')
        .attributes('href'),
    ).toBe('HTTPS://example.com')
  })

  it('has class icon-link on the anchor element', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    expect(w.get('a').classes()).toContain('icon-link')
  })

  it('always uses rel noopener and noreferrer for external links', () => {
    const w = mount(IconLink, {
      props: { icon: 'github', href: 'https://example.com', label: 'GitHub' },
    })
    const rel = w.get('a').attributes('rel')
    expect(rel).toContain('noopener')
    expect(rel).toContain('noreferrer')
  })
})
