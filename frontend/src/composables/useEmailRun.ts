import { onBeforeUnmount, watch } from 'vue'
import type { EmailRun, EmailRunState } from '@/utils/gradingAPI'

/** How often a page checks on a run while it sends. */
const CHECK_MS = 2000

/**
 * A bulk email's run sends on the server, so the page can be closed. While
 * ``state`` says it's sending, this checks back every few seconds
 * (``refresh``), and once it stops, hands ``onFinished`` the finished run, if
 * this page saw it sending.
 */
export function useEmailRun(
  state: () => EmailRunState | null | undefined,
  refresh: () => Promise<unknown>,
  onFinished: (run: EmailRun) => void
) {
  let timer: ReturnType<typeof setInterval> | null = null
  const stop = () => {
    if (timer !== null) clearInterval(timer)
    timer = null
  }
  watch(
    () => Boolean(state()?.sending),
    (sending, was) => {
      stop()
      if (sending) {
        timer = setInterval(() => void refresh(), CHECK_MS)
      } else if (was) {
        const run = state()?.run
        if (run) onFinished(run)
      }
    }
  )
  onBeforeUnmount(stop)
}
