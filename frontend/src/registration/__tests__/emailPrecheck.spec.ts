import { describe, expect, it, vi } from 'vitest'

import {
  formatSecondsRemaining,
  readEmailCheckJobId,
  readEmailCheckStatus,
  runEmailCheck,
  type EmailCheckClient,
  type EmailCheckStatus,
} from '@/registration/emailPrecheck'

const status = (value: string, extra: Partial<EmailCheckStatus> = {}): EmailCheckStatus => ({
  status: value,
  done: 0,
  total: 4,
  estimatedSecondsRemaining: null,
  ...extra,
})

const client = (jobId: string | null, polls: Array<EmailCheckStatus | null>): EmailCheckClient => ({
  start: vi.fn(async () => jobId),
  poll: vi.fn(async () => polls.shift() ?? null),
})

const run = (checker: EmailCheckClient, onProgress = vi.fn()) =>
  runEmailCheck(checker, onProgress, { intervalMs: 1, sleep: async () => {} })

describe('checking emails before submitting', () => {
  it('waits for a job to finish, reporting it queued then running', async () => {
    const onProgress = vi.fn()
    const checker = client('job-1', [
      status('queued'),
      status('running', { done: 1, estimatedSecondsRemaining: 9 }),
      status('running', { done: 3, estimatedSecondsRemaining: 2 }),
      status('done', { done: 4 }),
    ])

    expect(await run(checker, onProgress)).toBe('checked')
    expect(onProgress.mock.calls.map(([progress]) => progress)).toEqual([
      { phase: 'queued', done: 0, total: 4 },
      { phase: 'running', done: 1, total: 4, secondsRemaining: 9 },
      { phase: 'running', done: 3, total: 4, secondsRemaining: 2 },
    ])
    expect(checker.poll).toHaveBeenCalledWith('job-1')
  })

  it('skips the check when there is no job to wait for', async () => {
    const checker = client(null, [])

    expect(await run(checker)).toBe('skipped')
    expect(checker.poll).not.toHaveBeenCalled()
  })

  it.each(['failed', 'stalled', 'not_found', 'disabled', 'something new'])(
    'skips the check when the job is %s',
    async (value) => {
      expect(await run(client('job-1', [status('running'), status(value)]))).toBe('skipped')
    },
  )

  it('skips the check when a poll can’t be read', async () => {
    expect(await run(client('job-1', [status('queued'), null]))).toBe('skipped')
  })

  it('skips the check when starting or polling throws', async () => {
    const failingStart: EmailCheckClient = {
      start: vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
      poll: vi.fn(),
    }
    const failingPoll: EmailCheckClient = {
      start: vi.fn(async () => 'job-1'),
      poll: vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    }

    expect(await run(failingStart)).toBe('skipped')
    expect(await run(failingPoll)).toBe('skipped')
  })

  it('waits the poll interval between polls', async () => {
    const sleep = vi.fn(async () => {})
    await runEmailCheck(client('job-1', [status('queued'), status('done')]), vi.fn(), {
      intervalMs: 1000,
      sleep,
    })

    expect(sleep).toHaveBeenCalledExactlyOnceWith(1000)
  })
})

describe('reading the check’s answers', () => {
  it('reads a job id only from an answer that has one', () => {
    expect(readEmailCheckJobId({ status: 'started', jobId: 'abc' })).toBe('abc')
    expect(readEmailCheckJobId({ status: 'disabled' })).toBeNull()
    expect(readEmailCheckJobId({ jobId: '' })).toBeNull()
    expect(readEmailCheckJobId(['abc'])).toBeNull()
  })

  it('reads a status defensively', () => {
    expect(
      readEmailCheckStatus({ status: 'running', done: 2, total: 5, estimatedSecondsRemaining: 7 }),
    ).toEqual({ status: 'running', done: 2, total: 5, estimatedSecondsRemaining: 7 })
    expect(
      readEmailCheckStatus({ status: 'queued', done: -1, total: 'x', estimatedSecondsRemaining: null }),
    ).toEqual({ status: 'queued', done: 0, total: 0, estimatedSecondsRemaining: null })
    expect(readEmailCheckStatus({ done: 1 })).toBeNull()
    expect(readEmailCheckStatus('done')).toBeNull()
  })

  it('formats the time left as a countdown', () => {
    expect(formatSecondsRemaining(null)).toBe('')
    expect(formatSecondsRemaining(0)).toBe('Almost done')
    expect(formatSecondsRemaining(45)).toBe('About 45 s left')
    expect(formatSecondsRemaining(44.2)).toBe('About 45 s left')
    expect(formatSecondsRemaining(120)).toBe('About 2 min left')
    expect(formatSecondsRemaining(125)).toBe('About 2 min 5 s left')
  })
})
