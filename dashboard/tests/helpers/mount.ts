import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory, type RouteRecordRaw } from 'vue-router'
import { mount, type ComponentMountingOptions } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import type { Component, Plugin } from 'vue'

export function mountWithProviders<T extends Component>(
  component: T,
  options: ComponentMountingOptions<T> = {},
  routes: RouteRecordRaw[] = [{ path: '/', component: { template: '<div />' } }],
) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: 0 } },
  })
  const extraPlugins = (options.global?.plugins ?? []) as Plugin[]
  return mount(component, {
    ...options,
    global: {
      ...(options.global ?? {}),
      plugins: [
        createPinia(),
        router,
        [VueQueryPlugin, { queryClient }],
        ...extraPlugins,
      ],
    },
  })
}
