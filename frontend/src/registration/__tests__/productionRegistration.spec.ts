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

  it("sends a mentor's or supervisor's own confirmed warnings with theirs", () => {
    const forms = createRegistrationForms()
    const mentor = buildProductionRegistrationRequest(buildRegistrationRequest('mentor', forms), {
      'mentor.overrides.ConfirmEmailInvalidOverride': true,
      'mentor.overrides.ConfirmNameEmailOverride': true,
    })
    expect(mentor.payload).toHaveProperty('mentor.overrides', {
      ConfirmEmailInvalidOverride: true,
      ConfirmNameEmailOverride: true,
    })
    const supervisor = buildProductionRegistrationRequest(buildRegistrationRequest('supervisor', forms), {
      'supervisor.overrides.ConfirmNameEmailOverride': true,
    })
    expect(supervisor.payload).toHaveProperty('supervisor.overrides', { ConfirmNameEmailOverride: true })
    // None confirmed: none sent.
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('supervisor', forms)).payload,
    ).not.toHaveProperty('supervisor.overrides')
    // Another's confirmation isn't theirs.
    expect(() =>
      buildProductionRegistrationRequest(buildRegistrationRequest('mentor', forms), {
        'students.0.overrides.ConfirmEmailInvalidOverride': true,
      }),
    ).toThrow('Invalid registration warning override.')
  })

  it("sends a student group's held code token, for the group to take", () => {
    const forms = createRegistrationForms()
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms)).payload,
    ).not.toHaveProperty('group.codeToken')
    forms.studentTeam.groupCode = '482915'
    forms.studentTeam.groupCodeToken = 'held-token'
    const request = buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms))
    expect(request.payload).toHaveProperty('group.codeToken', 'held-token')
    expect(JSON.stringify(request)).not.toContain('482915')
  })

  it('joins a group by its code with only the student, and none of its own details', () => {
    const forms = createRegistrationForms()
    Object.assign(forms.studentTeam, {
      joinCode: ' 482915 ',
      groupCodeToken: 'held-token',
      supervisor: { firstName: 'Sam', lastName: 'Teacher', email: 'sam@example.com' },
    })
    const request = buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms))
    expect(request.payload).toHaveProperty('group', { joinCode: '482915' })
    expect(request.payload).toHaveProperty('students.length', 1)
    expect(request.payload).not.toHaveProperty('supervisor')
  })

  it('always sends supervisor details when registering individually or creating a group', () => {
    const forms = createRegistrationForms()
    for (const journey of ['student_individual', 'student_team'] as const) {
      expect(
        buildProductionRegistrationRequest(buildRegistrationRequest(journey, forms)).payload,
      ).toHaveProperty('supervisor', { firstName: '', lastName: '', email: '' })
    }
    Object.assign(forms.studentIndividual.supervisor, {
      firstName: 'Sam',
      lastName: 'Teacher',
      email: 'sam@example.com',
    })
    const request = buildProductionRegistrationRequest(
      buildRegistrationRequest('student_individual', forms),
    )
    expect(request.payload).toHaveProperty('supervisor', {
      firstName: 'Sam',
      lastName: 'Teacher',
      email: 'sam@example.com',
    })
    expect(request.payload).not.toHaveProperty('supervisorMode')
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
    // A student group has no shared interests.
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms)).payload,
    ).not.toHaveProperty('group.interests')
  })

  it('keeps incomplete peers incomplete and sets only allowlisted explicit overrides', () => {
    const forms = createRegistrationForms()
    // Left empty, Member 2 isn't registered; given a name, they are.
    expect(
      buildProductionRegistrationRequest(buildRegistrationRequest('student_team', forms)).payload,
    ).toHaveProperty('students.length', 1)
    Object.assign(forms.studentTeam.teammates[0]!, { firstName: 'Jamie', email: 'jamie@example.test' })
    const request = buildRegistrationRequest('student_team', forms)
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

  it("sends the guardian-has-an-account and the named supervisor's name confirmations", () => {
    const request = buildRegistrationRequest('student_individual', createRegistrationForms())
    const normalized = buildProductionRegistrationRequest(request, {
      'students.0.overrides.ConfirmGuardianEmailHasAccountOverride': true,
      'students.0.overrides.ConfirmSupervisorNameEmailOverride': true,
    })
    expect(normalized.payload).toHaveProperty('students.0.overrides', {
      ConfirmGuardianEmailHasAccountOverride: true,
      ConfirmSupervisorNameEmailOverride: true,
    })
  })

  it("sends Member 1's own interests, and guardian details only when enabled", () => {
    const forms = createRegistrationForms()
    forms.studentTeam.creator.interests = ['Biomedical Innovations']
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
    expect(normalized.payload).toHaveProperty('students.0.interests', ['Biomedical Innovations'])
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
  it("sends a mentor's checks and signature, and no older compliance or attestation details", () => {
    const forms = createRegistrationForms()
    const request = buildProductionRegistrationRequest(buildRegistrationRequest('mentor', forms))
    for (const field of ['usydEngineering', 'studentId', 'dateOfBirth', 'wwccNumber', 'indigenous', 'languages', 'signature'])
      expect(request.payload).toHaveProperty(`mentor.${field}`)
    for (const field of ['safeguardingJurisdiction', 'indigenousStatus', 'complianceDeclaration', 'attestation'])
      expect(request.payload).not.toHaveProperty(`mentor.${field}`)
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
