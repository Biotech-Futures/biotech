import { describe, expect, it } from 'vitest'

import { describeRun } from '@/composables/useEmailRun'
import type { EmailRun } from '@/utils/managementAPI'

const run = (overrides: Partial<EmailRun> = {}): EmailRun => ({
  due: 3,
  emailed: 3,
  failed: 0,
  error: '',
  missed: [],
  started_at: '2026-10-22T01:00:00Z',
  finished_at: '2026-10-22T01:02:00Z',
  ...overrides
})

const wording = { emailed: ['person', 'people'] as [string, string], failed: 'team', button: 'Send' }

describe('describeRun', () => {
  it('says when the mail server limited how many could go at once', () => {
    expect(describeRun(run({ limited: true }), wording).text).toBe(
      'Emailed 3 people. The mail server limited how many could go at once, so it sent more slowly.'
    )
  })

  it('says nothing of it otherwise', () => {
    expect(describeRun(run(), wording).text).toBe('Emailed 3 people.')
  })
})
