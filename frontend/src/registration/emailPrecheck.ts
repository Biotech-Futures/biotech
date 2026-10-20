/**
 * Checking a registration's email addresses before it's submitted
 * (POST /api/v1/registration/email-check/, then polling the job it starts), so
 * the person registering can correct any that don't exist while they wait.
 * The registration then comes back with a warning for each such address.
 *
 * The check never holds a registration up. Anything but a job that finishes
 * — the check switched off, registration closed, too many addresses, a job
 * that fails or stalls, an error or no connection — means "skipped", and the
 * registration is submitted as it would be without it.
 */

export type EmailCheckProgress =
  /** Waiting for earlier checks to finish before this one starts. */
  | { phase: 'queued'; done: number; total: number }
  | { phase: 'running'; done: number; total: number; secondsRemaining: number | null }

export type EmailCheckOutcome = 'checked' | 'skipped'

export interface EmailCheckClient {
  /** Start a check: its job's id, or null if there's no check to wait for. */
  start(): Promise<string | null>
  /** One poll of the job's progress, or null if it can't be read. */
  poll(jobId: string): Promise<EmailCheckStatus | null>
}

export interface EmailCheckStatus {
  status: string
  done: number
  total: number
  estimatedSecondsRemaining: number | null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const count = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0

/** A poll's answer, read defensively: null if it isn't one. */
export const readEmailCheckStatus = (data: unknown): EmailCheckStatus | null => {
  if (!isRecord(data) || typeof data.status !== 'string') return null
  const seconds = data.estimatedSecondsRemaining
  return {
    status: data.status,
    done: count(data.done),
    total: count(data.total),
    estimatedSecondsRemaining:
      typeof seconds === 'number' && Number.isFinite(seconds) && seconds >= 0 ? seconds : null,
  }
}

/** A start's answer: the job's id, or null for anything without one. */
export const readEmailCheckJobId = (data: unknown): string | null =>
  isRecord(data) && typeof data.jobId === 'string' && data.jobId ? data.jobId : null

export const POLL_INTERVAL_MS = 1000

/**
 * Start the check and poll it until it's done (``checked``) or there's no
 * point waiting (``skipped``), reporting progress as it goes. Never throws.
 */
export const runEmailCheck = async (
  client: EmailCheckClient,
  onProgress: (progress: EmailCheckProgress) => void,
  { intervalMs = POLL_INTERVAL_MS, sleep = (ms: number) => new Promise((done) => setTimeout(done, ms)) } = {},
): Promise<EmailCheckOutcome> => {
  try {
    const jobId = await client.start()
    if (!jobId) return 'skipped'
    for (;;) {
      const job = await client.poll(jobId)
      if (!job) return 'skipped'
      if (job.status === 'done') return 'checked'
      if (job.status === 'queued') {
        onProgress({ phase: 'queued', done: job.done, total: job.total })
      } else if (job.status === 'running') {
        onProgress({
          phase: 'running',
          done: job.done,
          total: job.total,
          secondsRemaining: job.estimatedSecondsRemaining,
        })
      } else {
        // failed, stalled, not found, disabled, or anything new: don't wait.
        return 'skipped'
      }
      await sleep(intervalMs)
    }
  } catch {
    return 'skipped'
  }
}

/** "About 2 min 5 s left", for a countdown. */
export const formatSecondsRemaining = (seconds: number | null): string => {
  if (seconds === null) return ''
  const whole = Math.max(0, Math.ceil(seconds))
  if (whole === 0) return 'Almost done'
  const minutes = Math.floor(whole / 60)
  const rest = whole % 60
  if (!minutes) return `About ${rest} s left`
  return rest ? `About ${minutes} min ${rest} s left` : `About ${minutes} min left`
}
