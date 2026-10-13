import { defineComponent, h, Suspense } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import ErrorBoundary from '@/components/base/ErrorBoundary.vue'
import { newTestQueryClient } from '../../helpers/mount'

const { stub, state } = vi.hoisted(() => ({
  state: {
    lengths: [] as { length: number; count: number }[],
    failComposition: false,
    top: {} as Record<string, { username?: string; password?: string; count: number }[]>,
  },
  stub: (key: string, data: unknown) => (o: unknown) => ({
    queryKey: [key, o],
    queryFn: async () => data,
  }),
}))

vi.mock('@/api/generated/@tanstack/vue-query.gen', () => ({
  statsTopCredentialsOptions: (o: { query: { by: string; outcome?: string } }) => ({
    queryKey: ['top', o],
    queryFn: async () => state.top[o.query.by + (o.query.outcome ? `:${o.query.outcome}` : '')] ?? [],
  }),
  statsAuthOutcomesOptions: stub('outcomes', { total: 10, successful: 1, failed: 9, success_rate: 10, unique_passwords: 3, unique_usernames: 2 }),
  statsPasswordsByLengthOptions: stub('bylen', []),
  statsPasswordCompositionOptions: (o: unknown) => ({
    queryKey: ['comp', o],
    queryFn: async () => {
      if (state.failComposition) throw { message: 'Too many requests', code: 429 }
      return {
        capped_at: 6,
        classes: [],
        // Lengths 0, 1 and 6 are empty: they render as disabled bars.
        lengths: state.lengths,
      }
    },
  }),
}))

import CredentialsView from '@/views/CredentialsView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/credentials', component: { template: '<div />' } }],
})

let wrapper: VueWrapper | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

const LENGTHS = [
  { length: 2, count: 3 },
  { length: 3, count: 9 },
  { length: 4, count: 5 },
]

async function mountView() {
  await router.replace('/credentials')
  wrapper = mount(
    defineComponent({
      render: () => h(ErrorBoundary, null, () => h(Suspense, null, { default: () => h(CredentialsView) })),
    }),
    {
      attachTo: document.body,
      global: {
        plugins: [router, [VueQueryPlugin, { queryClient: newTestQueryClient() }]],
        stubs: { PageShell: { template: '<div><slot name="head" /><slot /></div>' }, TopBar: true },
      },
    },
  )
  await flushPromises()
}

const bars = () => [...document.querySelectorAll<HTMLButtonElement>('.hist-col')]
const chip = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('.toggle-row button')].find((b) =>
    b.textContent!.trim().startsWith(label),
  )!
const stops = () => bars().filter((b) => !b.disabled && b.tabIndex === 0)
const press = async (key: string) => {
  document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  await flushPromises()
}

describe('CredentialsView password-length histogram', () => {
  it('is one Tab stop (the tallest bar) and arrows walk the non-empty bars', async () => {
    state.lengths = LENGTHS
    await mountView()
    expect(bars()).toHaveLength(7)
    expect(stops()).toHaveLength(1)
    expect(stops()[0]).toBe(bars()[3])

    bars()[3]!.focus()
    await press('ArrowRight')
    expect(document.activeElement).toBe(bars()[4])
    await press('ArrowRight')
    expect(document.activeElement).toBe(bars()[4]) // clamps; empty bars are skipped
    await press('Home')
    expect(document.activeElement).toBe(bars()[2])
    expect(stops()).toEqual([bars()[2]])
  })

  it('walks left, jumps to End, and clamps at the first bar', async () => {
    state.lengths = LENGTHS
    await mountView()
    bars()[3]!.focus()
    await press('ArrowLeft')
    expect(document.activeElement).toBe(bars()[2])
    await press('ArrowLeft')
    expect(document.activeElement).toBe(bars()[2])
    await press('End')
    expect(document.activeElement).toBe(bars()[4])
  })

  it('names the most common length in the caption', async () => {
    state.lengths = LENGTHS
    await mountView()
    expect(document.querySelector('.hist-cap')!.textContent).toMatch(/most common: 3 characters\s+\u00b7\s+9/)
  })

  it('breaks a tie in favour of the shortest length', async () => {
    state.lengths = [
      { length: 2, count: 5 },
      { length: 3, count: 5 },
    ]
    await mountView()
    expect(stops()).toEqual([bars()[2]])
    expect(document.querySelector('.hist-cap')!.textContent).toContain('most common: 2 characters')
  })

  it('has no Tab stop and no caption when every length is empty', async () => {
    state.lengths = []
    await mountView()
    expect(bars().every((b) => b.disabled)).toBe(true)
    expect(stops()).toHaveLength(0)
    expect(document.querySelector('.hist-cap')).toBeNull()
  })

  it('drops a drilled-in length when the anatomy tab changes', async () => {
    state.lengths = LENGTHS
    await mountView()
    bars()[3]!.click()
    await flushPromises()
    expect(document.querySelector('.drill')).not.toBeNull()

    chip('Composition').click()
    await flushPromises()
    chip('Length').click()
    await flushPromises()
    expect(document.querySelector('.drill')).toBeNull()
    expect(document.querySelector('.hist')).not.toBeNull()
  })
})

describe('CredentialsView when a query fails', () => {
  it('shows the API error instead of crashing on the missing data', async () => {
    state.failComposition = true
    try {
      await mountView()
    } finally {
      state.failComposition = false
    }
    expect(document.querySelector('[role="alert"]')!.textContent).toContain('Too many requests')
  })
})

describe('CredentialsView matrix cell drawer', () => {
  it('gives each label a title so a long password can be read in full', async () => {
    const pw = 'correct-horse-battery-staple-extra-long'
    state.top = {
      username: [{ username: 'root', count: 5 }],
      password: [{ password: pw, count: 5 }],
      pair: [{ username: 'root', password: pw, count: 5 }],
    }
    try {
      await mountView()
    } finally {
      state.top = {}
    }
    document
      .querySelector<SVGPolygonElement>('.mcell')!
      .dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    const titles = [...document.querySelectorAll<HTMLElement>('.pd-grid .k')].map((el) =>
      el.getAttribute('title'),
    )
    expect(titles).toEqual([`root, all passwords`, `${pw}, all usernames`])
  })
})
