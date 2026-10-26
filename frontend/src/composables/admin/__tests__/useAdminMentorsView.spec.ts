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
  it('lists only mentors whose accounts are active', () => {
    // The Status column is gone: a deactivated mentor is managed from the Users
    // page, so this list never shows one. Their group still needs a mentor,
    // which is what inactiveGroups below is for.
    const view = useAdminMentorsView()
    view.mentors.value = [
      buildMentor({ mentorId: 1, name: 'Active', isActive: true, lastMessageAt: '2026-01-01T00:00:00Z' }),
      buildMentor({ mentorId: 2, name: 'Deactivated', isActive: false, lastMessageAt: '2026-01-01T00:00:00Z' })
    ]

    expect(mentorIds(view.sortedMentors.value)).toEqual([1])
  })

  it('offers both deactivated and idle mentors for replacement', () => {
    // The two screens used to disagree because one counted deactivated
    // accounts and the other counted silence. Both belong here.
    const view = useAdminMentorsView()
    const recent = new Date().toISOString()
    view.mentors.value = [
      buildMentor({ mentorId: 1, name: 'Fine', isActive: true, lastMessageAt: recent, currentAssignedCount: 1 }),
      buildMentor({ mentorId: 2, name: 'Deactivated', isActive: false, lastMessageAt: recent, currentAssignedCount: 1 }),
      // Mentors a group below, so the count has to say so: silence is only
      // held against a mentor who has somewhere to break it.
      buildMentor({ mentorId: 3, name: 'Idle', isActive: true, lastMessageAt: '2020-01-01T00:00:00Z', currentAssignedCount: 1 })
    ]
    view.matchedGroups.value = [1, 2, 3].map((id) => ({
      membershipId: id * 10,
      groupId: id,
      groupName: `BTF${id}`,
      countryName: 'Australia',
      studentCount: 1,
      students: [],
      mentor: {
        mentorId: id,
        name: `M${id}`,
        isActive: id !== 2,
        lastMessageAt: id === 3 ? '2020-01-01T00:00:00Z' : recent,
        countryName: 'Australia',
        institution: null
      }
    }))

    expect(view.inactiveGroups.value.map((g) => g.groupId).sort()).toEqual([2, 3])
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
})
