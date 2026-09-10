import { describe, expect, it } from 'vitest'
import { useAdminMentorsView } from '@/composables/admin/useAdminMentorsView'
import type { AdminMentorDetail } from '@/utils/adminAPI'

const buildMentor = (overrides: Partial<AdminMentorDetail> = {}): AdminMentorDetail => ({
  mentorId: 1,
  firstName: 'Ada',
  lastName: 'Lovelace',
  name: 'Ada Lovelace',
  email: 'ada@example.com',
  isActive: true,
  institution: 'State University',
  countryName: 'Australia',
  maxGroupCount: 2,
  currentAssignedCount: 0,
  remainingCapacity: 2,
  interests: [],
  lastMessageAt: null,
  hasLoggedIn: false,
  lastLogin: null,
  availability: [],
  certificates: [],
  ...overrides
})

const mentorIds = (mentors: AdminMentorDetail[]) => mentors.map((mentor) => mentor.mentorId)

describe('useAdminMentorsView sorting', () => {
  it('sorts Status by displayed account active status', () => {
    const view = useAdminMentorsView()
    view.mentors.value = [
      buildMentor({
        mentorId: 1,
        name: 'Active Old Message',
        isActive: true,
        lastMessageAt: '2025-01-01T00:00:00Z'
      }),
      buildMentor({
        mentorId: 2,
        name: 'Inactive Recent Message',
        isActive: false,
        lastMessageAt: '2026-01-01T00:00:00Z'
      })
    ]

    view.setSort('status')

    expect(mentorIds(view.sortedMentors.value)).toEqual([2, 1])
  })

  it('sorts Logged In by No before Yes, then by last login date', () => {
    const view = useAdminMentorsView()
    view.mentors.value = [
      buildMentor({
        mentorId: 1,
        name: 'Recent Login',
        hasLoggedIn: true,
        lastLogin: '2026-03-01T00:00:00Z'
      }),
      buildMentor({
        mentorId: 2,
        name: 'Never Logged In',
        hasLoggedIn: false,
        lastLogin: null
      }),
      buildMentor({
        mentorId: 3,
        name: 'Older Login',
        hasLoggedIn: true,
        lastLogin: '2026-01-01T00:00:00Z'
      })
    ]

    view.setSort('loggedIn')

    expect(mentorIds(view.sortedMentors.value)).toEqual([2, 3, 1])
  })

  it('reverses Logged In sorting when selected again', () => {
    const view = useAdminMentorsView()
    view.mentors.value = [
      buildMentor({
        mentorId: 1,
        name: 'Recent Login',
        hasLoggedIn: true,
        lastLogin: '2026-03-01T00:00:00Z'
      }),
      buildMentor({
        mentorId: 2,
        name: 'Never Logged In',
        hasLoggedIn: false,
        lastLogin: null
      }),
      buildMentor({
        mentorId: 3,
        name: 'Older Login',
        hasLoggedIn: true,
        lastLogin: '2026-01-01T00:00:00Z'
      })
    ]

    view.setSort('loggedIn')
    view.setSort('loggedIn')

    expect(mentorIds(view.sortedMentors.value)).toEqual([1, 3, 2])
  })

  it('reports neutral and active sort direction icon classes', () => {
    const view = useAdminMentorsView()

    expect(view.sortIcon('country')).toBe('fa-sort')
    expect(view.sortIcon('name')).toBe('fa-sort-up')

    view.setSort('name')

    expect(view.sortIcon('name')).toBe('fa-sort-down')
  })
})
