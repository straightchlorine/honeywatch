import { onScopeDispose, ref, type Ref } from 'vue'

/** Live `prefers-reduced-motion: reduce` state; gate every animation on it. */
export function useReducedMotion(): Ref<boolean> {
  const mql =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null
  const reduced = ref(mql?.matches ?? false)

  function onChange(e: MediaQueryListEvent): void {
    reduced.value = e.matches
  }

  mql?.addEventListener('change', onChange)
  // Tests call this outside a component scope; silence disposal failure.
  onScopeDispose(() => mql?.removeEventListener('change', onChange), true)

  return reduced
}
