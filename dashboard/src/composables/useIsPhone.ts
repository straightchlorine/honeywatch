import { onScopeDispose, ref, type Ref } from 'vue'
import { LIST_PHONE_MQ } from '@/utils/breakpoints'

export function useIsPhone(): Ref<boolean> {
  const mql = typeof matchMedia === 'function' ? matchMedia(LIST_PHONE_MQ) : null
  const isPhone = ref(mql?.matches ?? false)
  const onChange = (e: MediaQueryListEvent): void => {
    isPhone.value = e.matches
  }
  mql?.addEventListener('change', onChange)
  onScopeDispose(() => mql?.removeEventListener('change', onChange), true)
  return isPhone
}
