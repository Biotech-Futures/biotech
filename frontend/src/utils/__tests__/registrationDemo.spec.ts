import { describe, expect, it } from 'vitest'

import {
  CSV_HEADERS,
  buildRegistrationDemoRequest,
  createRegistrationDemoForms,
  findCrossRoleEmailConflicts,
  parseRegistrationCsv,
  registrationCsvTemplate,
} from '@/utils/registrationDemo'
import { buildRegistrationRequest } from '@/registration/registrationGateway'

describe('registration demo factories', () => {
  it('starts group journeys at the required two-student minimum', () => {
    const forms = createRegistrationDemoForms()

    expect(forms.studentTeam.teammates).toHaveLength(1)
    expect(forms.supervisorGroup.students).toHaveLength(2)
    expect(forms.mentor.safeguardingStatus).toBe('pending-review')
  })

  it('builds backend-compatible team, group, and included CSV collections', () => {
    const forms = createRegistrationDemoForms()
    forms.supervisorCsv.rows = parseRegistrationCsv(registrationCsvTemplate()).rows

    const team = buildRegistrationDemoRequest('student_team', forms).payload as {
      creator: unknown
      teammates: unknown[]
    }
    const group = buildRegistrationDemoRequest('supervisor_group', forms).payload as {
      students: unknown[]
    }
    const csv = buildRegistrationDemoRequest('supervisor_csv', forms).payload as {
      rows: unknown[]
    }

    expect(team.creator).toBeDefined()
    expect(team.teammates).toHaveLength(1)
    expect(group.students).toHaveLength(2)
    expect(csv.rows).toHaveLength(1)
  })
})

describe('parseRegistrationCsv', () => {
  it('parses quoted values and classifies complete rows as valid', () => {
    const template = registrationCsvTemplate().replace(
      'Example Secondary College',
      '"Example Secondary College, Sydney"',
    )
    const result = parseRegistrationCsv(template)

    expect(result.errors).toEqual([])
    expect(result.rows).toHaveLength(1)
    expect(result.rows[0].values.school).toBe('Example Secondary College, Sydney')
    expect(result.rows[0].category).toBe('valid')
  })

  it('separates review-required and invalid rows', () => {
    const base = Object.fromEntries(CSV_HEADERS.map((header) => [header, ''])) as Record<
      (typeof CSV_HEADERS)[number],
      string
    >
    const review = {
      ...base,
      first_name: 'Sam',
      last_name: 'Lee',
      email: 'sam@example.edu.au',
      school: 'Example School',
      year_level: '11',
      country: 'Australia',
      interests: 'Space & Astrobiology',
      grouping_preference: 'cross_school',
    }
    const invalid = { ...review, email: 'not-an-email', year_level: '8' }
    const encode = (row: typeof review) =>
      CSV_HEADERS.map((header) => {
        const value = row[header]
        return value.includes(',') ? `"${value}"` : value
      }).join(',')
    const result = parseRegistrationCsv(
      `${CSV_HEADERS.join(',')}\n${encode(review)}\n${encode(invalid)}`,
    )

    expect(result.rows.map((row) => row.category)).toEqual(['review-required', 'invalid'])
    expect(result.rows[0].issues[0]).toContain('Guardian details are deferred')
  })

  it('rejects files that do not use the prescribed headers', () => {
    const result = parseRegistrationCsv('name,email\nAlex,alex@example.com')

    expect(result.rows).toEqual([])
    expect(result.errors[0]).toContain('Missing columns')
  })

  it('rejects duplicate expected headers while allowing flexible header order', () => {
    const reorderedHeaders = [...CSV_HEADERS].reverse()
    const duplicateEmailHeaders = [...reorderedHeaders, 'email']
    const result = parseRegistrationCsv(duplicateEmailHeaders.join(','))

    expect(result.rows).toEqual([])
    expect(result.errors).toContain('Duplicate columns: email.')
    expect(result.errors.some((error) => error.startsWith('Missing columns'))).toBe(false)
  })
})

describe('registration payload and email rules', () => {
  it('blocks a student address reused by an adult role', () => {
    const forms = createRegistrationDemoForms()
    forms.studentIndividual.student.email = 'student@example.com'
    forms.studentIndividual.supervisor.email = 'STUDENT@example.com'

    expect(findCrossRoleEmailConflicts('student_individual', forms)).toEqual([
      'Student email must be different from the supervisor email.',
    ])
  })

  it('normalizes emails and persists photo metadata without confirmation fields', () => {
    const forms = createRegistrationDemoForms()
    forms.studentIndividual.student.email = ' Student@Example.com '
    forms.studentIndividual.student.emailConfirm = 'Student@Example.com'
    forms.studentIndividual.student.profilePhoto = {
      name: 'profile.png',
      type: 'image/png',
      size: 2048,
    }

    const request = buildRegistrationDemoRequest('student_individual', forms)
    const payload = request.payload as {
      student: {
        email: string
        emailConfirm?: string
        profilePhoto: { name: string; type: string; size: number }
      }
    }

    expect(payload.student.email).toBe('student@example.com')
    expect(payload.student.emailConfirm).toBeUndefined()
    expect(payload.student.profilePhoto).toEqual({
      name: 'profile.png',
      type: 'image/png',
      size: 2048,
    })
    expect(JSON.stringify(request)).not.toContain('data:image')
  })

  it('uses the same sanitizer for gateway and legacy requests', () => {
    const forms = createRegistrationDemoForms()
    forms.studentIndividual.student.email = ' Student@Example.com '
    forms.studentIndividual.student.emailConfirm = ' Student@Example.com '
    forms.studentIndividual.student.profilePhoto = {
      name: ' profile.png ',
      type: ' image/png ',
      size: 2048,
      file: new File(['photo'], 'profile.png', { type: 'image/png' }),
      previewUrl: 'blob:preview',
    } as typeof forms.studentIndividual.student.profilePhoto & {
      file: File
      previewUrl: string
    }

    const legacyRequest = buildRegistrationDemoRequest('student_individual', forms)
    const gatewayRequest = buildRegistrationRequest('student_individual', forms)

    expect(gatewayRequest).toEqual(legacyRequest)
    expect(JSON.stringify(legacyRequest)).not.toContain('emailConfirm')
    expect(JSON.stringify(legacyRequest)).not.toContain('previewUrl')
    expect(JSON.stringify(legacyRequest)).not.toContain('"file"')
  })

  it('excludes explicitly removed invalid CSV rows from the request', () => {
    const forms = createRegistrationDemoForms()
    const parsed = parseRegistrationCsv(registrationCsvTemplate())
    forms.supervisorCsv.rows = parsed.rows
    forms.supervisorCsv.excludedRowNumbers = [2]

    const request = buildRegistrationDemoRequest('supervisor_csv', forms)
    const gatewayRequest = buildRegistrationRequest('supervisor_csv', forms)
    expect((request.payload as { rows: unknown[] }).rows).toEqual([])
    expect(gatewayRequest).toEqual(request)
  })

  it('wraps mentor and guardian submitters in backend-discoverable objects', () => {
    const forms = createRegistrationDemoForms()
    forms.mentor.email = ' Mentor@Example.com '
    forms.guardianConsent.guardianEmail = ' Guardian@Example.com '

    const mentorRequest = buildRegistrationDemoRequest('mentor', forms)
    const guardianRequest = buildRegistrationDemoRequest('guardian_consent', forms)

    expect((mentorRequest.payload as { mentor: { email: string } }).mentor.email).toBe(
      'mentor@example.com',
    )
    expect((guardianRequest.payload as { guardian: { email: string } }).guardian.email).toBe(
      'guardian@example.com',
    )
  })
})
