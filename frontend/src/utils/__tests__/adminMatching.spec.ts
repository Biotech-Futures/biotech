import { describe, expect, it } from 'vitest'
import {
  normalizeAssignedCount,
  parseMentorRecommendations,
  parseStudentMatchData
} from '@/utils/adminMatching'

const student = (id: number, name: string, extra: Record<string, unknown> = {}) => ({
  id,
  name,
  ...extra
})

const group = (id: number, name: string, extra: Record<string, unknown> = {}) => ({
  id,
  groupName: name,
  ...extra
})

describe('parseStudentMatchData', () => {
  it('accepts the snake_case wrapper the backend actually sends', () => {
    const result = parseStudentMatchData({
      recommendations: [],
      unmatched_students: [{ student: student(7, 'Ava Nguyen'), reason: 'No overlap' }],
      not_full_groups: [
        { ...group(3, 'BTF3'), student_count: 2, available_seats: 3 }
      ]
    })

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data.unmatchedStudents).toHaveLength(1)
    expect(result.data.notFullGroups[0].availableSeats).toBe(3)
  })

  it('pivots flat per-student recommendations into per-group buckets', () => {
    const result = parseStudentMatchData({
      recommendations: [
        { student: student(1, 'Ava'), recommendGroup: group(10, 'BTF10'), score: 88 },
        { student: student(2, 'Liam'), recommendGroup: group(10, 'BTF10'), score: 81 },
        { student: student(3, 'Mia'), recommendGroup: group(11, 'BTF11'), score: 79 }
      ]
    })

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data.recommendations).toHaveLength(2)
    const btf10 = result.data.recommendations.find((entry) => entry.id === 10)
    expect(btf10?.recommendStudents).toHaveLength(2)
  })

  it('sends students with no recommended group to the unmatched list', () => {
    const result = parseStudentMatchData([
      { student: student(1, 'Ava'), recommendGroup: null, reason: 'NO_SHARED_INTEREST' }
    ])

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data.recommendations).toHaveLength(0)
    expect(result.data.unmatchedStudents[0].reason).toBe('NO_SHARED_INTEREST')
  })

  it('normalises the mixed casing on nested student records', () => {
    const result = parseStudentMatchData([
      {
        student: {
          user_id: 5,
          firstName: 'Wei',
          lastName: 'Zhang',
          country_name: 'Singapore',
          year_level: 10,
          interests: ['Biology', { interestDesc: 'Robotics' }]
        },
        recommendGroup: null
      }
    ])

    expect(result.ok).toBe(true)
    if (!result.ok) return
    const parsed = result.data.unmatchedStudents[0].student
    expect(parsed.id).toBe(5)
    expect(parsed.name).toBe('Wei Zhang')
    expect(parsed.country).toBe('Singapore')
    expect(parsed.yearLevel).toBe(10)
    expect(parsed.interests).toEqual(['Biology', 'Robotics'])
  })

  // The regression this whole schema exists for: the previous hand-written
  // normaliser defaulted a missing id to '', which Number() turned into 0, and
  // 0 passed a Number.isFinite() guard straight through to /match/confirm/.
  it('rejects a student with a missing id instead of coercing it to 0', () => {
    const result = parseStudentMatchData([
      { student: { name: 'Nameless' }, recommendGroup: null }
    ])

    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.message).toContain('Student matching')
  })

  it('rejects an empty-string id', () => {
    const result = parseStudentMatchData([
      { student: { id: '', name: 'Nameless' }, recommendGroup: null }
    ])

    expect(result.ok).toBe(false)
  })

  it('accepts a numeric id sent as a string', () => {
    const result = parseStudentMatchData([
      { student: { id: '42', name: 'Ava' }, recommendGroup: null }
    ])

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data.unmatchedStudents[0].student.id).toBe(42)
  })
})

describe('parseMentorRecommendations', () => {
  const recommendation = {
    group: {
      groupId: 11,
      groupName: 'BTF11',
      countryName: 'Australia',
      studentInterests: ['Biology'],
      studentCount: 2
    },
    recommendedMentor: {
      mentorId: 4,
      name: 'Felix Reyes',
      countryName: 'Australia',
      institution: 'University of Melbourne',
      interests: ['Biology'],
      remainingCapacity: 2
    },
    reason: 'Same country, shared interest',
    score: 118,
    scoreBreakdown: {
      baseScore: 100,
      countryPenalty: 0,
      interestBonus: 14,
      timezonePenalty: 0,
      capacityBonus: 4,
      objectiveScore: 118
    }
  }

  it('parses a recommendation with a mentor', () => {
    const result = parseMentorRecommendations([recommendation])

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data[0].recommendedMentor?.name).toBe('Felix Reyes')
    expect(result.data[0].scoreBreakdown?.capacityBonus).toBe(4)
  })

  it('allows a null mentor for groups the matcher could not place', () => {
    const result = parseMentorRecommendations([
      { ...recommendation, recommendedMentor: null, reason: 'No compatible mentor' }
    ])

    expect(result.ok).toBe(true)
    if (!result.ok) return
    expect(result.data[0].recommendedMentor).toBeNull()
  })

  it('fails loudly when the payload is not a list', () => {
    const result = parseMentorRecommendations({ recommendations: [] })
    expect(result.ok).toBe(false)
  })

  it('reports the offending field path', () => {
    const result = parseMentorRecommendations([
      { ...recommendation, group: { ...recommendation.group, groupId: 0 } }
    ])

    expect(result.ok).toBe(false)
    if (result.ok) return
    expect(result.message).toContain('groupId')
  })
})

describe('normalizeAssignedCount', () => {
  it('reads the snake_case key', () => {
    expect(normalizeAssignedCount({ assigned_count: 6 })).toBe(6)
  })

  it('reads the camelCase key', () => {
    expect(normalizeAssignedCount({ assignedCount: 3 })).toBe(3)
  })

  it('falls back to 0 for an unusable payload', () => {
    expect(normalizeAssignedCount(null)).toBe(0)
  })
})
