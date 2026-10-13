import { afterEach, describe, expect, it } from 'vitest'
import PageShell from '@/components/layout/PageShell.vue'
import { mountWithProviders } from '../../../helpers/mount'

const routes = [{ path: '/', component: { template: '<div />' }, meta: { title: 'Pulse' } }]
const mounted: { unmount: () => void }[] = []
const shell = async () => {
  const w = mountWithProviders(
    PageShell,
    { attachTo: document.body, slots: { default: '<p>x</p>' } },
    routes,
  )
  mounted.push(w)
  await w.vm.$nextTick()
  return w
}

afterEach(() => {
  while (mounted.length) mounted.pop()!.unmount()
})

describe('PageShell route-change a11y', () => {
  it('stays silent on the first load, then announces and focuses main on later mounts', async () => {
    const first = await shell()
    expect(first.get('[role="status"]').text()).toBe('')
    first.unmount()
    mounted.length = 0

    // A navigation mounts a fresh PageShell: the flag must survive across instances.
    const second = await shell()
    expect(second.get('[role="status"]').text()).not.toBe('')
    expect(document.activeElement).toBe(second.get('#main').element)
  })
})
