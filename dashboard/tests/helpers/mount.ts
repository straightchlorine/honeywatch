import { createRouter, createMemoryHistory, type RouteRecordRaw } from 'vue-router'
import { mount, type ComponentMountingOptions } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import type { Component, Plugin } from 'vue'

/**
 * Create a QueryClient with test defaults (no retries, infinite staleTime, zero gcTime)
 * to prevent flaky async behavior during tests.
 */
export function newTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: 0 } },
  })
}

export function mountWithProviders<T extends Component>(
  component: T,
  options: ComponentMountingOptions<T> = {},
  routes: RouteRecordRaw[] = [{ path: '/', component: { template: '<div />' } }],
) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  const queryClient = newTestQueryClient()
  const extraPlugins = (options.global?.plugins ?? []) as Plugin[]
  return mount(component, {
    ...options,
    global: {
      ...(options.global ?? {}),
      plugins: [router, [VueQueryPlugin, { queryClient }], ...extraPlugins],
    },
  })
}
