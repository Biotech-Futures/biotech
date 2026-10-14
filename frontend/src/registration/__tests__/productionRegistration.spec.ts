import { describe, expect, it } from 'vitest'
import {
  createRegistrationForms,
  parseRegistrationCsv,
  registrationCsvTemplate,
} from '../registration'
import { buildRegistrationRequest } from '../registrationGateway'
import { buildProductionRegistrationRequest, registrationFormPath } from '../productionRegistration'

const studentCsv = () =>
  `${registrationCsvTemplate()}Alex,Morgan,alex@example.test,High School,10,Australia,NSW,"Biomedical Innovations, AI & Robotics and Smart Systems",Taylor,Morgan,taylor@example.test,Parent,,\r\n`

describe('production registration normalization', () => {
  it('uses the same students array for each student journey and a separate mentor payload', () => {
    const forms = createRegistrationForms()
    forms.supervisorCsv.rows = parseRegistrationCsv(studentCsv()).rows
    for (const journey of [
      'student_individual',
      'student_team',
      'supervisor_individual',
      'supervisor_group',
      'supervisor_csv',
    ] as const) {
      const normalized = buildProductionRegistrationRequest(
        buildRegistrationRequest(journey, forms),
      )
      expect(normalized.payload).toHaveProperty('students')
      expect(normalized.payload).not.toHaveProperty('creator')
      expect(normalized.payload).not.toHaveProperty('teammates')
      expect(normalized.payload).not.toHaveProperty('rows')
      expect(JSON.stringify(normalized)).not.toContain('emailConfirm')
      expect(normalized.payload).toHaveProperty('source.method', journey)
    }
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('mentor', forms)).payload,
    ).toHaveProperty('mentor')
  })

  it('retains only included CSV records, original row numbers and manually chosen group interests', () => {
    const forms = createRegistrationForms()
    forms.supervisorCsv.rows = parseRegistrationCsv(studentCsv()).rows
    forms.supervisorCsv.rows[0]!.rowNumber = 12
    const csv = buildProductionRegistrationRequest(
      buildRegistrationRequest('supervisor_csv', forms),
    )
    expect(csv.payload).toHaveProperty('source.rowNumbers.0', 12)
    expect(JSON.stringify(csv)).not.toContain('category')
    expect(JSON.stringify(csv)).not.toContain('issues')
    forms.studentTeam.interests = ['Water & Energy Tech']
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms)).payload,
    ).toHaveProperty('group.interests', ['Water & Energy Tech'])
  })

  it('keeps incomplete peers incomplete and sets only allowlisted explicit overrides', () => {
    const request = buildRegistrationRequest('student_team', createRegistrationForms())
    const normalized = buildProductionRegistrationRequest(request, {
      'students.1.overrides.ConfirmNameEmailOverride': true,
    })
    expect(normalized.payload).toHaveProperty('students.1.school', '')
    expect(normalized.payload).toHaveProperty('students.1.overrides.ConfirmNameEmailOverride', true)
    expect(registrationFormPath(request, 'students.1.email')).toBe('studentTeam.teammates.0.email')
    expect(() =>
      buildProductionRegistrationRequest(request, { 'students.1.overrides.Approve': true }),
    ).toThrow()
  })

  it('sends group-only interests for the creator and optional guardian details only when enabled', () => {
    const forms = createRegistrationForms()
    forms.studentTeam.creator.interests = ['Biomedical Innovations']
    forms.studentTeam.interests = ['Water & Energy Tech']
    const peer = forms.studentTeam.teammates[0]!
    Object.assign(peer.guardian, {
      firstName: 'Casey',
      lastName: 'Rivera',
      email: 'casey@example.test',
      relationship: 'Parent',
    })
    let normalized = buildProductionRegistrationRequest(
      buildRegistrationRequest('student_team', forms),
    )
    expect(normalized.payload).toHaveProperty('students.0.interests', [])
    expect(normalized.payload).toHaveProperty('group.interests', ['Water & Energy Tech'])
    expect(normalized.payload).toHaveProperty('students.1.guardian.email', '')
    peer.guardianDeferred = false
    normalized = buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms))
    expect(normalized.payload).toHaveProperty('students.1.guardian.email', 'casey@example.test')
    expect(normalized.payload).toHaveProperty('students.1.guardianDeferred', false)
    expect(forms.studentTeam.creator.interests).toEqual(['Biomedical Innovations'])
  })

  it('normalizes quoted comma-separated CSV interests to the ordinary student array', () => {
    const forms = createRegistrationForms()
    forms.supervisorCsv.rows = parseRegistrationCsv(studentCsv()).rows
    const normalized = buildProductionRegistrationRequest(
      buildRegistrationRequest('supervisor_csv', forms),
    )
    expect(normalized.payload).toHaveProperty('students.0.interests', [
      'Biomedical Innovations',
      'AI & Robotics and Smart Systems',
    ])
    expect(normalized.payload).toHaveProperty('source.rowNumbers', [2])
  })
  it('does not send declined mentor demographics', () => {
    const forms = createRegistrationForms()
    Object.assign(forms.mentor, {
      languages: 'Private',
      languagesPreferNot: true,
      dateOfBirth: '1990-01-01',
      dateOfBirthPreferNot: true,
    })
    const request = buildProductionRegistrationRequest(buildRegistrationRequest('mentor', forms))
    expect(request.payload).toHaveProperty('mentor.languages', '')
    expect(request.payload).toHaveProperty('mentor.dateOfBirth', '')
  })

  it('does not assign a new grouping preference or replace server validation', () => {
    const forms = createRegistrationForms()
    const request = buildProductionRegistrationRequest(
      buildRegistrationRequest('supervisor_individual', forms),
    )
    expect(request.payload).toHaveProperty('students.0.groupingPreference', '')
    expect(request.payload).toHaveProperty('students.0.school', '')
    expect(request.payload).toHaveProperty('students.0.overrides', {})
  })
})
