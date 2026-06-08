import { defineAsyncComponent, type Component } from 'vue'
import { retryImport } from './retryImport'

/**
 * defineAsyncComponent that survives a transient chunk-fetch failure (retry +
 * backoff) and recovers from a stale deploy (guarded reload) via retryImport.
 * A permanent failure surfaces to the nearest ErrorBoundary.
 */
export function lazyComponent(loader: () => Promise<{ default: Component }>): Component {
  return defineAsyncComponent(() => retryImport(loader))
}
