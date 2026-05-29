import { describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mountWithProviders } from '../../helpers/mount'
import ErrorBoundary from '@/components/base/ErrorBoundary.vue'

describe('ErrorBoundary', () => {
  it('renders slot content when there is no error', () => {
    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h('div', { class: 'ok' }, 'fine') },
    })
    expect(w.find('.ok').exists()).toBe(true)
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('catches a child error, sanitizes the message, and recovers on reset', async () => {
    const boom = ref(true)
    const Child = defineComponent({
      setup() {
        return () => {
          if (boom.value) throw new Error('bad\x07message')
          return h('div', { class: 'recovered' }, 'ok')
        }
      },
    })

    const w = mountWithProviders(ErrorBoundary, {
      slots: { default: () => h(Child) },
    })
    await nextTick()

    expect(w.find('[role="alert"]').exists()).toBe(true)
    // Control char stripped from the rendered message.
    expect(w.text()).not.toContain('\x07')
    expect(w.text()).toContain('badmessage')

    boom.value = false
    await w.get('button').trigger('click')
    await nextTick()
    expect(w.find('.recovered').exists()).toBe(true)
  })
})
