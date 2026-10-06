import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStudentMatching } from '@/composables/admin/useStudentMatching'
import { confirmStudentAssignments, fetchStudentMatch } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({
  fetchStudentMatch: vi.fn(),
  confirmStudentAssignments: vi.fn()
}))

vi.mock('@/utils/apiError', () => ({
  logApiError: vi.fn()
}))

const recommendation = (
  id: number,
  name: string,
  group: { id: string | number; groupName: string }
) => ({
  student: { id, name, interests: [] },
  recommendGroup: { ...group, maxSize: 5, tutor: null, groupStudent: [] },
  reason: '',
  score: 90,
  scoreBreakdown: null
})

const newGroup = { id: 'new-Australia-1', groupName: 'Suggested Group 1' }

describe('useStudentMatching mode', () => {
  beforeEach(() => {
    vi.mocked(fetchStudentMatch).mockReset()
    vi.mocked(fetchStudentMatch).mockResolvedValue({
      recommendations: [recommendation(1, 'Ava Nguyen', newGroup)]
    })
  })

  it('runs in balanced mode by default', async () => {
    const matching = useStudentMatching()
    expect(matching.mode.value).toBe('balanced')

    await matching.run()
    expect(fetchStudentMatch).toHaveBeenCalledWith('balanced')
  })

  it('discards the previous board and error when the mode changes', async () => {
    const matching = useStudentMatching()
    await matching.run()
    matching.error.value = 'Stale error from the last mode'
    expect(matching.groups.value).toHaveLength(1)

    matching.setMode('strict')

    expect(matching.mode.value).toBe('strict')
    expect(matching.hasRun.value).toBe(false)
    expect(matching.groups.value).toEqual([])
    expect(matching.waiting.value).toEqual([])
    expect(matching.buckets.value).toEqual({})
    expect(matching.error.value).toBe('')

    // Reset must not resurrect the old mode's proposal.
    matching.reset()
    expect(matching.groups.value).toEqual([])

    await matching.run()
    expect(fetchStudentMatch).toHaveBeenLastCalledWith('strict')
  })
})

describe('useStudentMatching confirm', () => {
  beforeEach(() => {
    vi.mocked(fetchStudentMatch).mockReset()
    vi.mocked(confirmStudentAssignments).mockReset()
    vi.mocked(fetchStudentMatch).mockResolvedValue({
      recommendations: [recommendation(1, 'Ava Nguyen', newGroup)]
    })
    vi.mocked(confirmStudentAssignments).mockResolvedValue(undefined as never)
  })

  it('never submits assignments to an already-formed group', async () => {
    const matching = useStudentMatching()
    await matching.run()

    // The board never seeds a formed group, so plant one directly to exercise
    // the guard that stands behind it.
    const [ava] = matching.bucketFor(newGroup.id)
    matching.buckets.value = {
      ...matching.buckets.value,
      '10': [{ ...ava, student: { ...ava.student, id: 3, name: 'Omar Haddad' } }]
    }

    await expect(matching.confirm()).resolves.toBe(true)
    expect(confirmStudentAssignments).toHaveBeenCalledWith([
      { studentId: 1, groupId: 'new-Australia-1' }
    ])
  })

  it('refuses to confirm when only formed-group assignments remain', async () => {
    const matching = useStudentMatching()
    await matching.run()

    const [ava] = matching.bucketFor(newGroup.id)
    matching.buckets.value = { [newGroup.id]: [], '10': [ava] }

    await expect(matching.confirm()).resolves.toBe(false)
    expect(confirmStudentAssignments).not.toHaveBeenCalled()
    expect(matching.error.value).toBe('No assignments to confirm.')
  })
})
