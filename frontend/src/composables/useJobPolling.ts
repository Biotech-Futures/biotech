import { computed, onUnmounted, ref } from 'vue'
import {
  downloadJobResult,
  fetchJobStatus,
  startComponentDownload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

export type JobPhase = 'idle' | 'starting' | 'preparing' | 'downloading' | 'done' | 'failed'

/**
 * Drives an async grading download: kick off the job, poll its status every
 * 2s, and save the file once it's done. One job at a time per composable
 * instance; the interval is cleaned up on unmount or when a new job starts.
 */
export function useJobPolling() {
  const phase = ref<JobPhase>('idle')
  const error = ref('')

  let timer: number | null = null
  let checking = false

  const stop = () => {
    if (timer != null) {
      window.clearInterval(timer)
      timer = null
    }
    checking = false
  }

  const fail = (message: string) => {
    stop()
    phase.value = 'failed'
    error.value = message
  }

  const start = async (code: string, format: 'zip' | 'xlsx', groupIds?: number[]) => {
    stop()
    error.value = ''
    phase.value = 'starting'
    let jobId: number
    try {
      jobId = await startComponentDownload(code, format, groupIds)
    } catch (err) {
      fail(`Download failed: ${apiErrorFromUnknown(err).message}`)
      return
    }
    phase.value = 'preparing'
    timer = window.setInterval(async () => {
      if (checking) return
      checking = true
      try {
        const job = await fetchJobStatus(jobId)
        if (job.status === 'done') {
          stop()
          phase.value = 'downloading'
          await downloadJobResult(job)
          phase.value = 'done'
        } else if (job.status === 'failed') {
          fail(job.error || 'The export job failed.')
        }
      } catch (err) {
        fail(`Download failed: ${apiErrorFromUnknown(err).message}`)
      } finally {
        checking = false
      }
    }, 2000)
  }

  const isBusy = computed(
    () => phase.value === 'starting' || phase.value === 'preparing' || phase.value === 'downloading'
  )

  onUnmounted(stop)

  return { phase, error, isBusy, start }
}
