import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ANALYTICS_REFRESH_INTERVAL_MS } from '@/utils/analyticsRefresh'

export function useAnalyticsRefresh(refresh: () => Promise<unknown>) {
  const lastUpdated = ref<string | null>(null)
  const refreshFailed = ref(false)
  let timer: ReturnType<typeof setInterval> | undefined
  let refreshing = false
  let disposed = false

  const markUpdated = () => {
    if (!disposed) {
      lastUpdated.value = new Date().toISOString()
      refreshFailed.value = false
    }
  }
  const markRefreshFailed = () => {
    if (!disposed) refreshFailed.value = true
  }

  onMounted(() => {
    timer = setInterval(() => {
      if (refreshing) return

      const scrollX = window.scrollX
      const scrollY = window.scrollY
      refreshing = true
      void refresh()
        .then(async () => {
          await nextTick()
          if (!disposed) {
            window.scrollTo({ left: scrollX, top: scrollY, behavior: 'auto' })
          }
        })
        .catch(() => {})
        .finally(() => { refreshing = false })
    }, ANALYTICS_REFRESH_INTERVAL_MS)
  })

  onBeforeUnmount(() => {
    disposed = true
    clearInterval(timer)
  })

  return { lastUpdated, refreshFailed, markUpdated, markRefreshFailed }
}
