import { describe, expect, it } from 'vitest'
import type { AdminUser, GroupActivityResponse } from '@/utils/liveAnalyticsApi'
import { buildUsersAnalytics, schoolCounts } from '@/utils/liveAnalyticsData'

const baseUser: AdminUser = {
  id: 1, firstName: 'Sample', lastName: 'Student', email: 'student@example.test', role: 'student',
  country: null, state: null, groupId: null, groupName: null, schoolName: null,
  mentorBackground: null, mentorInstitution: null, mentorReason: null, mentorMaxGroupCount: null,
  yearLevel: null, joinPermissionReceived: true, guardianEmail: null, interests: [],
  isAdmin: false, isActive: true, hasLoggedIn: true, lastLogin: '2026-10-15T00:00:00Z',
  accountStatus: 'active', createdAt: '2026-08-01T00:00:00Z', invitedAt: '2026-08-01T00:00:00Z', activatedAt: '2026-08-01T00:00:00Z',
  supervisorName: null, supervisorEmail: null,
}

let nextId = 1
function user(schoolName: string | null, overrides: Partial<AdminUser> = {}): AdminUser {
  nextId += 1
  return { ...baseUser, id: nextId, schoolName, ...overrides }
}
const inState = (stateName: string) => ({ country: { countryName: 'Australia' }, state: { stateName } })
const inCountry = (countryName: string) => ({ country: { countryName }, state: null })

describe('schoolCounts', () => {
  it('counts students and supervisors per school, largest first', () => {
    expect(schoolCounts([
      user('Hill High', inState('NSW')),
      user('Hill High', inState('NSW')),
      user('Hill High', { ...inState('NSW'), role: 'supervisor' }),
      user('Bay College', inState('VIC')),
      user('Bay College', { ...inState('VIC'), role: 'supervisor' }),
      user('Lagos Academy', inCountry('Nigeria')),
    ])).toEqual([
      { name: 'Hill High', location: 'NSW', students: 2, supervisors: 1, total: 3 },
      { name: 'Bay College', location: 'VIC', students: 1, supervisors: 1, total: 2 },
      { name: 'Lagos Academy', location: 'Nigeria', students: 1, supervisors: 0, total: 1 },
    ])
  })

  it('places an Australian school by its state and any other school by its country', () => {
    const schools = schoolCounts([
      user('Perth Grammar', inState('WA')),
      user('Auckland Grammar', inCountry('New Zealand')),
      user('Lincoln High', inCountry('United States of America')),
    ])
    expect(Object.fromEntries(schools.map((school) => [school.name, school.location]))).toEqual({
      'Perth Grammar': 'WA',
      'Auckland Grammar': 'New Zealand',
      'Lincoln High': 'United States of America',
    })
  })

  it('shows Australia for an Australian school whose users gave no state, and Unknown with no location', () => {
    const schools = schoolCounts([
      user('Outback School', inCountry('Australia')),
      user('Mystery High'),
    ])
    expect(schools.find((school) => school.name === 'Outback School')?.location).toBe('Australia')
    expect(schools.find((school) => school.name === 'Mystery High')?.location).toBe('Unknown')
  })

  it('places a school where most of its users are, ignoring users with no location', () => {
    const [school] = schoolCounts([
      user('Border High', inState('QLD')),
      user('Border High', inState('NSW')),
      user('Border High', inState('NSW')),
      user('Border High'),
      user('Border High'),
      user('Border High'),
    ])
    expect(school).toMatchObject({ location: 'NSW', total: 6 })
  })

  it('breaks a location tie alphabetically, so the result does not depend on user order', () => {
    const users = [user('Twin High', inState('VIC')), user('Twin High', inState('NSW'))]
    expect(schoolCounts(users)[0].location).toBe('NSW')
    expect(schoolCounts([...users].reverse())[0].location).toBe('NSW')
  })

  it('treats names differing only in case or spacing as one school, named as most users wrote it', () => {
    const [school, ...others] = schoolCounts([
      user('Sydney Boys High', inState('NSW')),
      user('  sydney boys   high ', inState('NSW')),
      user('Sydney Boys High', inState('NSW')),
    ])
    expect(others).toEqual([])
    expect(school).toMatchObject({ name: 'Sydney Boys High', students: 3 })
  })

  it('leaves out mentors, admins and users without a school', () => {
    expect(schoolCounts([
      user('Hill High', { ...inState('NSW'), role: 'mentor' }),
      user('Hill High', { ...inState('NSW'), role: 'admin' }),
      user(null, inState('NSW')),
      user('   ', inState('NSW')),
    ])).toEqual([])
  })

  it('sorts schools with the same total by name', () => {
    expect(schoolCounts([
      user('Zeta College', inState('NSW')),
      user('Alpha College', inState('NSW')),
    ]).map((school) => school.name)).toEqual(['Alpha College', 'Zeta College'])
  })
})

describe('buildUsersAnalytics schools', () => {
  it('only counts users registered by the selected year', () => {
    const noActivity: GroupActivityResponse = {
      messages_by_group: [], messages_by_user: [], messages_by_day: [], messages_by_group_by_day: [],
      mentor_count: 0, student_count: 0, students_per_mentor: null,
      average_group_size_by_year: [], group_summary_by_year: [], query_range: { start: null, end: null },
    }
    const bundle = {
      users: [
        user('Hill High', { ...inState('NSW'), createdAt: '2025-03-01T00:00:00Z' }),
        user('Hill High', { ...inState('NSW'), createdAt: '2026-03-01T00:00:00Z' }),
      ],
      groupActivity: noActivity,
    }
    expect(buildUsersAnalytics(bundle, 2025).schools).toEqual([
      { name: 'Hill High', location: 'NSW', students: 1, supervisors: 0, total: 1 },
    ])
    expect(buildUsersAnalytics(bundle, 2026).schools[0].total).toBe(2)
  })
})
