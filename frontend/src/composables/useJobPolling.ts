import { computed, onUnmounted, ref } from 'vue'
import {
  downloadJobResult,
  fetchJobStatus,
  startAllSubmissionsDownload,
  startComponentDownload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

export type JobPhase = 'idle' | 'starting' | 'preparing' | 'downloading' | 'done' | 'failed'

/** Gaps between status checks: quick at first, since most exports finish in
 *  well under a second, then every 2s so a long job doesn't flood the server. */
export const POLL_DELAYS_MS = [250, 500, 1000, 2000]

/**
 * Drives an async grading download: kick off the job, check its status
 * (see POLL_DELAYS_MS), and save the file once it's done. One job at a time
 * per composable instance; checks stop on unmount or when a new job starts.
 */
export function useJobPolling() {
  const phase = ref<JobPhase>('idle')
  const error = ref('')

  let timer: number | null = null
  // Bumped by every stop, so a check still in flight for an abandoned job
  // (a newer one started, or the page closed) knows to do nothing.
  let currentRun = 0

  const stop = () => {
    currentRun++
    if (timer != null) {
      window.clearTimeout(timer)
      timer = null
    }
  }

  const fail = (message: string) => {
    stop()
    phase.value = 'failed'
    error.value = message
  }

  const begin = async (startJob: () => Promise<number>) => {
    stop()
    const run = currentRun
    error.value = ''
    phase.value = 'starting'
    let jobId: number
    try {
      jobId = await startJob()
    } catch (err) {
      if (run === currentRun) fail(`Download failed: ${apiErrorFromUnknown(err).message}`)
      return
    }
    if (run !== currentRun) return
    phase.value = 'preparing'

    let checks = 0
    const scheduleCheck = () => {
      const delay = POLL_DELAYS_MS[Math.min(checks, POLL_DELAYS_MS.length - 1)]
      checks++
      timer = window.setTimeout(check, delay)
    }
    const check = async () => {
      timer = null
      try {
        const job = await fetchJobStatus(jobId)
        if (run !== currentRun) return
        if (job.status === 'done') {
          phase.value = 'downloading'
          await downloadJobResult(job)
          if (run === currentRun) phase.value = 'done'
        } else if (job.status === 'failed') {
          fail(job.error || 'The export job failed.')
        } else {
          scheduleCheck()
        }
      } catch (err) {
        if (run === currentRun) fail(`Download failed: ${apiErrorFromUnknown(err).message}`)
      }
    }
    scheduleCheck()
  }

  const start = (code: string, format: 'zip' | 'xlsx', groupIds?: number[]) =>
    begin(() => startComponentDownload(code, format, groupIds))

  // The everything-zip: every group, every component.
  const startAll = () => begin(() => startAllSubmissionsDownload())

  const isBusy = computed(
    () => phase.value === 'starting' || phase.value === 'preparing' || phase.value === 'downloading'
  )

  onUnmounted(stop)

  return { phase, error, isBusy, start, startAll }
}
