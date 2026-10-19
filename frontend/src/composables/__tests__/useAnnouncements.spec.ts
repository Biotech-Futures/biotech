import { describe, expect, it } from 'vitest'
import {
  getAudienceClass,
  getAudienceLabel,
  normalizeAnnouncement
} from '@/composables/useAnnouncements'

describe('normalizeAnnouncement audience', () => {
  it('keeps every targeted role, in a stable order', () => {
    const announcement = normalizeAnnouncement({
      id: 1,
      title: 'All hands',
      body: '<p>Hello</p>',
      visibility_scope: 'role_based',
      published_at: '2026-05-01T10:00:00Z',
      audiences: [
        { role: 3, role_name: 'Supervisor' },
        { role: 1, role_name: 'Student' },
        { role: 2, role_name: 'Mentor' }
      ]
    })

    expect(announcement.audienceRoles).toEqual(['student', 'mentor', 'supervisor'])
    expect(announcement.audience).toBe('student,mentor,supervisor')
    expect(getAudienceLabel(announcement.audience)).toBe('Student, Mentor, Supervisor')
  })

  it('keeps the saved role and group ids for editing', () => {
    const announcement = normalizeAnnouncement({
      id: 2,
      title: 'Group only',
      body: '<p>Hello</p>',
      visibility_scope: 'role_based',
      published_at: '2026-05-01T10:00:00Z',
      audiences: [
        { role: 2, role_name: 'Mentor', group: null, group_name: null },
        { role: null, role_name: null, group: 10, group_name: 'Team Alpha' }
      ]
    })

    expect(announcement.audiences).toEqual([
      { roleId: 2, groupId: null, roleName: 'Mentor', groupName: null },
      { roleId: null, groupId: 10, roleName: null, groupName: 'Team Alpha' }
    ])
  })

  it('labels a single role as before and defaults to All Users', () => {
    const mentor = normalizeAnnouncement({
      id: 3,
      title: 'Mentors',
      body: '<p>Hi</p>',
      visibility_scope: 'role_based',
      audiences: [{ role: 2, role_name: 'Mentor' }]
    })
    expect(mentor.audience).toBe('mentor')
    expect(getAudienceLabel(mentor.audience)).toBe('Mentor')
    expect(getAudienceClass(mentor.audience)).toBe('status-warning')

    const global = normalizeAnnouncement({
      id: 4,
      title: 'Everyone',
      body: '<p>Hi</p>',
      visibility_scope: 'global',
      audiences: []
    })
    expect(global.audience).toBe('global')
    expect(getAudienceLabel(global.audience)).toBe('All Users')
    expect(getAudienceClass(global.audience)).toBe('status-active')
  })
})
