import { describe, expect, it } from 'vitest'
import type { DemoMentor } from '@/types/analytics'
import { mentorActivity, mentorSnapshot } from '@/utils/mentorsAnalytics'

function mentor(id: string, overrides: Partial<DemoMentor> = {}): DemoMentor {
  return {
    id,
    name: `Mentor ${id}`,
    status: 'active',
    background: 'industry',
    capacity: 3,
    groupIds: [],
    studentIds: [],
    region: null,
    interests: [],
    institution: null,
    accountActive: true,
    lastLogin: null,
    ...overrides,
  }
}

const groups = (count: number) => Array.from({ length: count }, (_, index) => `g${index}`)
const students = (count: number) => Array.from({ length: count }, (_, index) => `s${index}`)

describe('mentorSnapshot', () => {
  it('buckets groups and students by the 5-group and 25-student limits', () => {
    const snapshot = mentorSnapshot([
      mentor('1'),
      mentor('2', { groupIds: groups(1), studentIds: students(5) }),
      mentor('3', { groupIds: groups(5), studentIds: students(25) }),
    ], [], '2026-10-17', '2026-10-17')

    expect(snapshot.groups.map((bucket) => bucket.label)).toEqual(['0', '1', '2', '3', '4', '5'])
    expect(snapshot.groups.map((bucket) => bucket.value)).toEqual([1, 1, 0, 0, 0, 1])
    expect(snapshot.students.map((bucket) => bucket.label)).toEqual(['0', '1–5', '6–10', '11–15', '16–20', '21–25'])
    expect(snapshot.students.map((bucket) => bucket.value)).toEqual([1, 1, 0, 0, 0, 1])
  })

  it('adds over-limit buckets only when a mentor is above the limit', () => {
    const snapshot = mentorSnapshot(
      [mentor('1', { groupIds: groups(6), studentIds: students(26) })],
      [],
      '2026-10-17',
      '2026-10-17',
    )

    expect(snapshot.groups[snapshot.groups.length - 1]).toEqual({ label: 'Over 5', value: 1 })
    expect(snapshot.students[snapshot.students.length - 1]).toEqual({ label: 'Over 25', value: 1 })
  })

  it('measures last login from the mentor account rather than login events', () => {
    const snapshot = mentorSnapshot([
      mentor('1', { lastLogin: '2026-10-15T09:00:00Z' }),
      mentor('2', { lastLogin: '2026-08-01T09:00:00Z' }),
      mentor('3', { lastLogin: null }),
    ], [{ mentorId: '3', date: '2026-10-16', logins: 1, messages: 0 }], '2026-09-30', '2026-10-17')

    expect(snapshot.lastLogin).toEqual([
      { label: '0–7 days', value: 1 },
      { label: '8–30 days', value: 0 },
      { label: '31–90 days', value: 1 },
      { label: '90+ days', value: 0 },
      { label: 'Never logged in', value: 1 },
    ])
  })

  it('falls back to login events when the source has no account last login', () => {
    const withoutLogin = mentor('1')
    delete withoutLogin.lastLogin
    const snapshot = mentorSnapshot(
      [withoutLogin],
      [{ mentorId: '1', date: '2026-10-10', logins: 1, messages: 0 }],
      '2026-10-17',
    )

    expect(snapshot.lastLogin[0]).toEqual({ label: '0–7 days', value: 1 })
  })

  it('sums the capacity of activated mentors only', () => {
    const snapshot = mentorSnapshot([
      mentor('1', { capacity: 5, groupIds: groups(2) }),
      mentor('2', { capacity: 3, groupIds: groups(4) }),
      mentor('3', { capacity: 4, groupIds: groups(1), accountActive: false, status: 'inactive' }),
    ], [], '2026-10-17', '2026-10-17')

    expect(snapshot.capacityPool).toEqual({
      activatedMentors: 2,
      totalSlots: 8,
      usedSlots: 6,
      openSlots: 3,
      utilisation: 75,
    })
    expect(snapshot.capacity).toEqual([
      { label: 'Available capacity', value: 1 },
      { label: 'At capacity', value: 0 },
      { label: 'Over capacity', value: 1 },
    ])
  })
})

describe('mentorActivity', () => {
  it('ranks every activated mentor, including those without messages', () => {
    const activity = mentorActivity([
      mentor('1', { name: 'Ava' }),
      mentor('2', { name: 'Ben' }),
      mentor('3', { name: 'Cleo', accountActive: false }),
    ], [
      { mentorId: '2', date: '2026-10-01', logins: 0, messages: 4 },
      { mentorId: '3', date: '2026-10-01', logins: 0, messages: 9 },
    ], { start: '2026-01-01', end: '2026-10-17' })

    expect(activity.ranking).toEqual([
      { id: '2', name: 'Ben', messages: 4 },
      { id: '1', name: 'Ava', messages: 0 },
    ])
  })
})
