import { describe, expect, it } from 'vitest'

import {
  CSV_HEADERS,
  createPendingPeer,
  createRegistrationForms,
  findCrossRoleEmailConflicts,
  parseRegistrationCsv,
  parseRegistrationInterests,
  registrationCsvTemplate,
  revalidateRegistrationCsvRows,
} from '@/registration/registration'
import { buildRegistrationRequest } from '@/registration/registrationGateway'

const studentCsv = () =>
  `${registrationCsvTemplate()}Alex,Morgan,alex.morgan@example.edu.au,Example Secondary College,10,Australia,NSW,"Biomedical Innovations, AI & Robotics and Smart Systems",Taylor,Morgan,taylor.morgan@example.com,Parent,,\r\n`

describe('registration form factories', () => {
  it('does not assign the deferred grouping preference in the form or CSV template', () => {
    expect(createRegistrationForms().supervisorIndividual.groupingPreference).toBe('')
    expect(parseRegistrationCsv(studentCsv()).rows[0].values.grouping_preference).toBe('')
  })

  it('starts every group member as Member 1, with their guardian optional', () => {
    const forms = createRegistrationForms()
    expect(forms.studentTeam.creator.country).toBe('Australia')
    for (const peer of [forms.studentTeam.teammates[0], createPendingPeer()]) {
      expect(peer).toMatchObject({
        school: '',
        yearLevel: '',
        country: 'Australia',
        state: '',
        interests: [],
        guardianDeferred: true,
      })
    }
  })
  it('starts group journeys at the required two-student minimum', () => {
    const forms = createRegistrationForms()

    expect(forms.studentTeam.teammates).toHaveLength(1)
    expect(forms.supervisorGroup.students).toHaveLength(2)
  })

  it('builds backend-compatible team, group, and included CSV collections', () => {
    const forms = createRegistrationForms()
    forms.supervisorCsv.rows = parseRegistrationCsv(studentCsv()).rows

    const team = buildRegistrationRequest('student_team', forms).payload as {
      creator: unknown
      teammates: unknown[]
    }
    const group = buildRegistrationRequest('supervisor_group', forms).payload as {
      students: unknown[]
    }
    const csv = buildRegistrationRequest('supervisor_csv', forms).payload as {
      rows: unknown[]
    }

    expect(team.creator).toBeDefined()
    expect(team.teammates).toHaveLength(1)
    expect(group.students).toHaveLength(2)
    expect(csv.rows).toHaveLength(1)
  })
})

describe('parseRegistrationCsv', () => {
  it('downloads an empty template without sample people or grouping choices', () => {
    expect(registrationCsvTemplate()).toBe(`${CSV_HEADERS.join(',')}\r\n`)
    expect(parseRegistrationCsv(registrationCsvTemplate()).errors).toEqual([
      'The CSV has a header row but no student rows.',
    ])
  })

  it('parses quoted comma-separated interests and preserves legacy separators', () => {
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    expect(row.category).toBe('valid')
    expect(parseRegistrationInterests(row.values.interests)).toEqual([
      'Biomedical Innovations',
      'AI & Robotics and Smart Systems',
    ])
    for (const separator of [',', '|', ';']) {
      expect(
        parseRegistrationInterests(` Biomedical Innovations ${separator} Water & Energy Tech `),
      ).toEqual(['Biomedical Innovations', 'Water & Energy Tech'])
    }
  })
  it('revalidates corrected fields without losing row identity or entered spaces', () => {
    const rows = parseRegistrationCsv(studentCsv()).rows
    rows[0].values.email = 'invalid'
    rows[0].values.year_level = '8'
    const invalid = revalidateRegistrationCsvRows(rows)
    expect(invalid[0].category).toBe('invalid')
    expect(invalid[0].fieldErrors).toMatchObject({
      email: 'Student email format is invalid.',
      year_level: 'Year level must be 9, 10, 11, or 12.',
    })
    invalid[0].values.email = 'corrected@example.test'
    invalid[0].values.year_level = '11'
    invalid[0].values.first_name = 'Alex '
    const corrected = revalidateRegistrationCsvRows(invalid)
    expect(corrected[0]).toMatchObject({
      rowNumber: 2,
      category: 'valid',
      issues: [],
      fieldErrors: {},
    })
    expect(corrected[0].values.first_name).toBe('Alex ')
  })

  it('updates every affected duplicate row after editing, excluding and reincluding', () => {
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    const rows = [
      row,
      {
        ...row,
        rowNumber: 3,
        values: { ...row.values, email: ` ${row.values.email.toUpperCase()} ` },
      },
    ]
    const duplicate = revalidateRegistrationCsvRows(rows)
    expect(duplicate.map((entry) => entry.category)).toEqual(['invalid', 'invalid'])
    expect(revalidateRegistrationCsvRows(duplicate, [3])[0].category).toBe('valid')
    expect(revalidateRegistrationCsvRows(duplicate, [3]).map((entry) => entry.rowNumber)).toEqual([
      2, 3,
    ])
    expect(revalidateRegistrationCsvRows(duplicate).map((entry) => entry.category)).toEqual([
      'invalid',
      'invalid',
    ])
    duplicate[1].values.email = 'different@example.test'
    expect(revalidateRegistrationCsvRows(duplicate).map((entry) => entry.category)).toEqual([
      'valid',
      'valid',
    ])
  })

  it('rechecks guardian conflicts and review-only fields after corrections', () => {
    const row = parseRegistrationCsv(studentCsv()).rows[0]
    const peer = { ...row, rowNumber: 3, values: { ...row.values, email: 'peer@example.test' } }
    row.values.guardian_email = peer.values.email
    expect(revalidateRegistrationCsvRows([row, peer])[0].fieldErrors?.guardian_email).toContain(
      'cannot be listed as a guardian',
    )
    expect(revalidateRegistrationCsvRows([row, peer], [3])[0].category).toBe('valid')
    row.values.guardian_email = 'guardian@example.test'
    row.values.interests = 'Unknown interest'
    expect(revalidateRegistrationCsvRows([row, peer])[0].category).toBe('review-required')
    row.values.interests = 'Biomedical Innovations'
    expect(revalidateRegistrationCsvRows([row, peer])[0].category).toBe('valid')
  })

  it('rejects more than 500 student rows', () => {
    const [header, example] = studentCsv().trim().split('\n')
    const rows = Array.from({ length: 501 }, (_, index) =>
      example.replace(/[^,]+@[^,]+/, `student-${index}@example.test`),
    )
    const accepted = parseRegistrationCsv([header, ...rows.slice(0, 500)].join('\n'))
    expect(accepted.rows).toHaveLength(500)
    expect(accepted.rows.every((row) => row.category === 'valid')).toBe(true)
    expect(parseRegistrationCsv([header, ...rows].join('\n')).errors).toEqual([
      'Upload no more than 500 students per CSV.',
    ])
  })
  it('parses quoted values and classifies complete rows as valid', () => {
    const template = studentCsv().replace(
      'Example Secondary College',
      '"Example Secondary College, Sydney"',
    )
    const result = parseRegistrationCsv(template)

    expect(result.errors).toEqual([])
    expect(result.rows).toHaveLength(1)
    expect(result.rows[0].values.school).toBe('Example Secondary College, Sydney')
    expect(result.rows[0].category).toBe('valid')
  })

  it('preserves original line numbers across blank lines and quoted multiline cells', () => {
    const [header, row] = studentCsv().trim().split('\r\n')
    const multiline = row.replace('Example Secondary College', '"Example Secondary\nCollege"')
    const next = row.replace('alex.morgan@example.edu.au', 'second@example.test')
    const result = parseRegistrationCsv(`\r\n${header}\r\n\r\n${multiline}\r\n\r\n${next}\r\n`)
    expect(result.errors).toEqual([])
    expect(result.rows.map((entry) => entry.rowNumber)).toEqual([4, 7])
    expect(result.rows[0].values.school).toBe('Example Secondary\nCollege')
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
      state: 'NSW',
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
  it('checks optional member guardians against every student without checking hidden contacts', () => {
    const forms = createRegistrationForms()
    forms.studentTeam.creator.email = 'creator@example.test'
    const peer = forms.studentTeam.teammates[0]
    peer.email = 'peer@example.test'
    peer.guardian.email = 'creator@example.test'
    expect(findCrossRoleEmailConflicts('student_team', forms)).toEqual([])
    peer.guardianDeferred = false
    expect(findCrossRoleEmailConflicts('student_team', forms)[0]).toContain('member 2 guardian')
  })
  it('blocks a student address reused by an adult role', () => {
    const forms = createRegistrationForms()
    forms.studentIndividual.student.email = 'student@example.com'
    forms.studentIndividual.supervisor.email = 'STUDENT@example.com'

    expect(findCrossRoleEmailConflicts('student_individual', forms)).toEqual([
      'Student email must be different from the supervisor email.',
    ])
  })

  it('normalizes emails and persists photo metadata without confirmation fields', () => {
    const forms = createRegistrationForms()
    forms.studentIndividual.student.email = ' Student@Example.com '
    forms.studentIndividual.student.emailConfirm = 'Student@Example.com'
    forms.studentIndividual.student.profilePhoto = {
      name: 'profile.png',
      type: 'image/png',
      size: 2048,
    }

    const request = buildRegistrationRequest('student_individual', forms)
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

  it('removes client-only payload values through the shared sanitizer', () => {
    const forms = createRegistrationForms()
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

    const gatewayRequest = buildRegistrationRequest('student_individual', forms)

    expect(JSON.stringify(gatewayRequest)).not.toContain('emailConfirm')
    expect(JSON.stringify(gatewayRequest)).not.toContain('previewUrl')
    expect(JSON.stringify(gatewayRequest)).not.toContain('"file"')
  })

  it('excludes explicitly removed invalid CSV rows from the request', () => {
    const forms = createRegistrationForms()
    const parsed = parseRegistrationCsv(studentCsv())
    forms.supervisorCsv.rows = parsed.rows
    forms.supervisorCsv.excludedRowNumbers = [2]

    const request = buildRegistrationRequest('supervisor_csv', forms)
    expect((request.payload as { rows: unknown[] }).rows).toEqual([])
  })

  it('wraps mentor submissions in a backend-discoverable object', () => {
    const forms = createRegistrationForms()
    forms.mentor.email = ' Mentor@Example.com '

    const mentorRequest = buildRegistrationRequest('mentor', forms)

    expect((mentorRequest.payload as { mentor: { email: string } }).mentor.email).toBe(
      'mentor@example.com',
    )
  })
})
