import { afterEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '@/utils/adminAPI'
import { applyImportCheck, useImportEmailCheck, type ImportRowCheck } from '@/utils/importEmailCheck'

const rows = [
  { row: 2, email: 'a@example.test', firstName: 'A', lastName: 'One' },
  { row: 3, email: 'b@example.test', firstName: 'B', lastName: 'Two' },
]
const results: ImportRowCheck[] = [
  { row: 2, problems: ['Account email already exists'], warnings: [] },
  { row: 3, problems: [], warnings: [{ field: 'email', message: "The student's email couldn't be verified." }] },
]

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useImportEmailCheck', () => {
  it('follows the lookups, then asks again for the mailbox warnings', async () => {
    const post = vi
      .spyOn(adminApi, 'adminPost')
      .mockResolvedValueOnce({ results: [], lookups: { jobId: 'job-1', status: 'started', total: 2, done: 0 } })
      .mockResolvedValueOnce({ results, lookups: null })
    const get = vi
      .spyOn(adminApi, 'adminGet')
      .mockResolvedValueOnce({ status: 'running', total: 2, done: 1 })
      .mockResolvedValueOnce({ status: 'done', total: 2, done: 2, errors: 1 })
    const check = useImportEmailCheck('students', { pollMs: 0 })

    const checked = await check.check(rows)

    expect(post.mock.calls.map(([path, body]) => [path, (body as { lookup: boolean }).lookup])).toEqual([
      ['/user/import-check/', true],
      ['/user/import-check/', false],
    ])
    expect(get).toHaveBeenCalledWith('/user/import-check/job-1/')
    expect(checked?.get(3)?.warnings).toHaveLength(1)
    expect(check.state).toMatchObject({ checking: false, done: 2, total: 2, note: "1 email couldn't be checked." })
  })

  it('uses the first answer when every address was on file', async () => {
    const post = vi.spyOn(adminApi, 'adminPost').mockResolvedValueOnce({ results, lookups: null })
    const check = useImportEmailCheck('mentors', { pollMs: 0 })

    expect((await check.check(rows))?.get(2)?.problems).toEqual(['Account email already exists'])
    expect(post).toHaveBeenCalledTimes(1)
    expect(post.mock.calls[0]?.[1]).toMatchObject({ kind: 'mentors', lookup: true })
  })

  it("says so when the check can't be done, and gives nothing", async () => {
    vi.spyOn(adminApi, 'adminPost').mockRejectedValueOnce(new Error('offline'))
    const check = useImportEmailCheck('students', { pollMs: 0 })

    expect(await check.check(rows)).toBeNull()
    expect(check.state).toMatchObject({ checking: false, note: "The emails couldn't be checked. You can still import." })
  })

  it('drops an older check once a newer file is chosen', async () => {
    let answerFirst: (value: unknown) => void = () => {}
    vi.spyOn(adminApi, 'adminPost')
      .mockImplementationOnce(() => new Promise((resolve) => (answerFirst = resolve)))
      .mockResolvedValueOnce({ results, lookups: null })
    const check = useImportEmailCheck('students', { pollMs: 0 })

    const first = check.check(rows)
    const second = await check.check(rows)
    answerFirst({ results: [], lookups: null })

    expect(await first).toBeNull()
    expect(second?.size).toBe(2)
    expect(check.state.checking).toBe(false)
  })
})

describe('applyImportCheck', () => {
  it('moves refused rows to the skipped ones, in order, and keeps the warnings of the rest', () => {
    const parsed = [
      { rowNumber: 2, email: 'a@example.test' },
      { rowNumber: 3, email: 'b@example.test' },
    ]
    const checked = applyImportCheck(
      parsed,
      [{ rowNumber: 4, email: 'c@example.test', reason: 'missing school' }],
      new Map(results.map((result) => [result.row, result])),
    )

    expect(checked.valid).toEqual([parsed[1]])
    expect(checked.invalid).toEqual([
      { rowNumber: 2, email: 'a@example.test', reason: 'Account email already exists' },
      { rowNumber: 4, email: 'c@example.test', reason: 'missing school' },
    ])
    expect([...checked.warnings.keys()]).toEqual([3])
  })
})
