import { nextTick, onBeforeUnmount, onMounted, watch, type WatchSource } from 'vue'

type StateBinding = { value: unknown }
type StateBindings = Record<string, StateBinding>

interface StoredAnalyticsRefreshState {
  values: Record<string, unknown>
  scrollX: number
  scrollY: number
}

const STORAGE_PREFIX = 'btf.analytics.refreshState.'

function isPageReload() {
  if (typeof window === 'undefined') return false
  const navigation = window.performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
  return navigation?.type === 'reload'
}

function readStoredState(storageKey: string): StoredAnalyticsRefreshState | null {
  if (!isPageReload()) return null
  try {
    const raw = window.sessionStorage.getItem(storageKey)
    return raw ? JSON.parse(raw) as StoredAnalyticsRefreshState : null
  } catch {
    return null
  }
}

/**
 * Restores filters and scroll position only after a full browser refresh.
 * Normal Vue Router navigation therefore continues to use each page's defaults.
 */
export function useAnalyticsRefreshState(
  pageKey: string,
  bindings: StateBindings,
  ready: WatchSource<boolean>,
) {
  const storageKey = `${STORAGE_PREFIX}${pageKey}`
  const pendingState = readStoredState(storageKey)
  let restoreStarted = false

  function saveState() {
    const values = Object.fromEntries(
      Object.entries(bindings).map(([key, binding]) => [key, binding.value]),
    )
    const state: StoredAnalyticsRefreshState = {
      values,
      scrollX: window.scrollX,
      scrollY: window.scrollY,
    }
    window.sessionStorage.setItem(storageKey, JSON.stringify(state))
  }

  function applyValues() {
    if (!pendingState) return
    for (const [key, value] of Object.entries(pendingState.values)) {
      const binding = bindings[key]
      if (binding) binding.value = value
    }
  }

  async function restoreState() {
    if (!pendingState || restoreStarted) return
    restoreStarted = true
    window.sessionStorage.removeItem(storageKey)

    // Apply twice so dependent watchers (for example, view/year changes) can settle first.
    applyValues()
    await nextTick()
    applyValues()
    await nextTick()

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        window.scrollTo({ left: pendingState.scrollX, top: pendingState.scrollY, behavior: 'auto' })
      })
    })
  }

  const stopReadyWatch = watch(ready, (isReady) => {
    if (isReady) void restoreState()
  }, { immediate: true })

  onMounted(() => window.addEventListener('beforeunload', saveState))
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', saveState)
    stopReadyWatch()
  })
}
