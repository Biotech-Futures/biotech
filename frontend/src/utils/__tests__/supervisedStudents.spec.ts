import { describe, expect, it } from 'vitest'
import { classifyStudent, registrationLabel, type SupervisedStudent } from '@/utils/supervisedStudents'

const student = (overrides: Partial<SupervisedStudent> = {}): SupervisedStudent => ({
  id: 1,
  first_name: 'Ava',
  last_name: 'Nguyen',
  email: 'ava@example.com',
  school_name: 'Eastwood College',
  year_lvl: '10',
  interests: [],
  // A student added without a guardian has their own name copied in, and the
  // flag on, as every student is saved.
  pg_first_name: 'Ava',
  pg_last_name: 'Nguyen',
  pg_email: null,
  parent_guardian_flag: true,
  has_join_permission: false,
  joinperm_response_id: null,
  joinperm_granted_at: null,
  group_id: null,
  group_name: null,
  ...overrides,
})

describe('classifyStudent', () => {
  it('puts a student with no guardian email in Pending Parent/Guardian Details', () => {
    expect(classifyStudent(student())).toBe('pendingDetails')
    expect(classifyStudent(student({ pg_email: '  ' }))).toBe('pendingDetails')
    expect(registrationLabel(student())).toBe('Pending parent/guardian details')
  })

  it('puts a student whose guardian has an email in Pending Parent/Guardian Permission', () => {
    const named = student({ pg_first_name: 'Pat', pg_last_name: 'Nguyen', pg_email: 'pat@example.com' })
    expect(classifyStudent(named)).toBe('pendingPermission')
  })

  it('puts a student with consent in Fully Registered, whatever the guardian details', () => {
    expect(classifyStudent(student({ has_join_permission: true }))).toBe('fullyRegistered')
    expect(
      classifyStudent(student({ has_join_permission: true, pg_email: 'pat@example.com' })),
    ).toBe('fullyRegistered')
  })
})
