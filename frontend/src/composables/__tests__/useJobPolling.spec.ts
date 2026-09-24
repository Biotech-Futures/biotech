import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { useJobPolling } from '@/composables/useJobPolling'
import {
  downloadJobResult,
  fetchJobStatus,
  startAllSubmissionsDownload,
  startComponentDownload,
  type GradingJobDetail
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  startComponentDownload: vi.fn(),
  startAllSubmissionsDownload: vi.fn(),
  fetchJobStatus: vi.fn(),
  downloadJobResult: vi.fn()
}))

const startMock = vi.mocked(startComponentDownload)
const startAllMock = vi.mocked(startAllSubmissionsDownload)
const statusMock = vi.mocked(fetchJobStatus)
const downloadMock = vi.mocked(downloadJobResult)

const job = (status: GradingJobDetail['status'], error: string | null = null): GradingJobDetail => ({
  id: 11,
  kind: 'bulk_zip',
  status,
  download_url: status === 'done' ? '/api/v1/grading/jobs/11/download/' : null,
  error,
  created_at: '2026-09-23T00:00:00Z',
  finished_at: null
})

// The composable registers onUnmounted, so drive it from inside a real
// component the way every page does.
const mountPolling = () => {
  let polling!: ReturnType<typeof useJobPolling>
  const wrapper = mount(
    defineComponent({
      setup() {
        polling = useJobPolling()
        return () => null
      }
    })
  )
  return { wrapper, polling }
}

const tick = async (ms: number) => {
  await vi.advanceTimersByTimeAsync(ms)
}

beforeEach(() => {
  vi.useFakeTimers()
  startMock.mockReset()
  startAllMock.mockReset()
  statusMock.mockReset()
  downloadMock.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the happy path', () => {
  it('walks starting → preparing → downloading → done and saves the file', async () => {
    startMock.mockResolvedValueOnce(11)
    statusMock.mockResolvedValueOnce(job('running')).mockResolvedValueOnce(job('done'))
    downloadMock.mockResolvedValueOnce()

    const { polling } = mountPolling()
    expect(polling.phase.value).toBe('idle')
    expect(polling.isBusy.value).toBe(false)

    const run = polling.start('SAQ', 'zip', [1, 2])
    await Promise.resolve()
    await run
    expect(startMock).toHaveBeenCalledWith('SAQ', 'zip', [1, 2])
    expect(polling.phase.value).toBe('preparing')
    expect(polling.isBusy.value).toBe(true)

    await tick(2000) // first poll: still running
    expect(polling.phase.value).toBe('preparing')

    await tick(2000) // second poll: done → download
    expect(downloadMock).toHaveBeenCalledWith(expect.objectContaining({ id: 11 }))
    expect(polling.phase.value).toBe('done')
    expect(polling.isBusy.value).toBe(false)

    // The interval is stopped: no further status checks.
    statusMock.mockClear()
    await tick(6000)
    expect(statusMock).not.toHaveBeenCalled()
  })

  it('startAll drives the everything-zip through the same machinery', async () => {
    startAllMock.mockResolvedValueOnce(12)
    statusMock.mockResolvedValueOnce(job('done'))
    downloadMock.mockResolvedValueOnce()

    const { polling } = mountPolling()
    await polling.startAll()
    await tick(2000)
    expect(startAllMock).toHaveBeenCalled()
    expect(polling.phase.value).toBe('done')
  })
})

describe('failure paths', () => {
  it('a refused job start fails immediately without polling', async () => {
    startMock.mockRejectedValueOnce(new Error('too many jobs'))
    const { polling } = mountPolling()
    await polling.start('SAQ', 'zip')
    expect(polling.phase.value).toBe('failed')
    expect(polling.error.value).toContain('Download failed:')
    await tick(6000)
    expect(statusMock).not.toHaveBeenCalled()
  })

  it('a failed job surfaces its server error and stops polling', async () => {
    startMock.mockResolvedValueOnce(11)
    statusMock.mockResolvedValueOnce(job('failed', 'disk full'))
    const { polling } = mountPolling()
    await polling.start('SAQ', 'xlsx')
    await tick(2000)
    expect(polling.phase.value).toBe('failed')
    expect(polling.error.value).toBe('disk full')
  })

  it('a failed job with no message gets a readable default', async () => {
    startMock.mockResolvedValueOnce(11)
    statusMock.mockResolvedValueOnce(job('failed', null))
    const { polling } = mountPolling()
    await polling.start('SAQ', 'zip')
    await tick(2000)
    expect(polling.error.value).toBe('The export job failed.')
  })

  it('a poll that throws fails the run instead of retrying forever', async () => {
    startMock.mockResolvedValueOnce(11)
    statusMock.mockRejectedValueOnce(new Error('network down'))
    const { polling } = mountPolling()
    await polling.start('SAQ', 'zip')
    await tick(2000)
    expect(polling.phase.value).toBe('failed')
    statusMock.mockClear()
    await tick(6000)
    expect(statusMock).not.toHaveBeenCalled()
  })
})

describe('lifecycle', () => {
  it('starting a new job abandons the previous poll', async () => {
    startMock.mockResolvedValue(11)
    statusMock.mockResolvedValue(job('running'))
    const { polling } = mountPolling()
    await polling.start('SAQ', 'zip')
    await tick(2000)
    const pollsBefore = statusMock.mock.calls.length

    await polling.start('POSTER', 'zip')
    await tick(2000)
    // Only ONE interval is live: one extra poll, not two.
    expect(statusMock.mock.calls.length).toBe(pollsBefore + 1)
  })

  it('unmounting stops the poll so no request fires afterwards', async () => {
    startMock.mockResolvedValueOnce(11)
    statusMock.mockResolvedValue(job('running'))
    const { wrapper, polling } = mountPolling()
    await polling.start('SAQ', 'zip')
    await tick(2000)
    expect(statusMock).toHaveBeenCalled()

    wrapper.unmount()
    statusMock.mockClear()
    await tick(6000)
    expect(statusMock).not.toHaveBeenCalled()
  })
})
