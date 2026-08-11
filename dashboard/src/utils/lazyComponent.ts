import { defineAsyncComponent, type Component } from 'vue'
import { retryImport } from './retryImport'

/**
 * Wrap a component loader with resilience against chunk-fetch failures and stale deploys.
 *
 * Arguments:
 *   loader: function returning { default: Component }
 *
 * Returns:
 *   Vue async component
 */
export function lazyComponent(loader: () => Promise<{ default: Component }>): Component {
  return defineAsyncComponent(() => retryImport(loader))
}
