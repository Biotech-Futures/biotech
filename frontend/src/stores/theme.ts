import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { safeLocalStorageGet, safeLocalStorageSet } from '@/utils/storage'

const THEME_KEY = 'dashboard-surface-mode'

export const useThemeStore = defineStore('theme', () => {
  function resolveInitial(): 'day' | 'night' {
    const stored = safeLocalStorageGet(THEME_KEY, '')
    if (stored === 'day' || stored === 'night') return stored
    return 'night'
  }

  const mode = ref<'day' | 'night'>(resolveInitial())
  const isDayMode = computed(() => mode.value === 'day')

  function toggleMode() {
    mode.value = isDayMode.value ? 'night' : 'day'
    safeLocalStorageSet(THEME_KEY, mode.value)
  }

  return { mode, isDayMode, toggleMode }
})
