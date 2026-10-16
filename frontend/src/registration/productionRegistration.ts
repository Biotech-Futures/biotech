import {
  createStudent,
  isBlankStudent,
  parseRegistrationInterests,
  type StudentDetails,
  type RegistrationIntakeJourney,
  hasSupervisor,
} from './registration'
import type { RegistrationRequest } from './registrationGateway'

export const REGISTRATION_OVERRIDE_NAMES = [
  'ConfirmSchoolOverride',
  'ConfirmNameEmailOverride',
] as const

type OverrideName = (typeof REGISTRATION_OVERRIDE_NAMES)[number]
type SubmittedStudent = Omit<StudentDetails, 'emailConfirm'> & {
  groupingPreference?: string
  overrides?: Partial<Record<OverrideName, boolean>>
}

export const studentRequestPrefixes = (request: RegistrationRequest): string[] => {
  switch (request.journey) {
    case 'student_individual':
      return ['studentIndividual.student']
    case 'student_team':
      return [
        'studentTeam.creator',
        ...registeredTeammates(request).map((index) => `studentTeam.teammates.${index}`),
      ]
    case 'supervisor_individual':
      return ['supervisorIndividual.student']
    case 'supervisor_group':
      return request.payload.students.map((_, index) => `supervisorGroup.students.${index}`)
    case 'supervisor_csv':
      return request.payload.rows.map((_, index) => `supervisorCsv.rows.${index}`)
    case 'mentor':
      return []
  }
}

/** A student joining a registered group by its code, instead of creating one. */
const joiningGroup = (request: RegistrationRequest) =>
  request.journey === 'student_team' && Boolean(request.payload.joinCode?.trim())

/** The teammates registered with a student group (their places in it): none
 *  when joining one, and none left empty. */
const registeredTeammates = (request: RegistrationRequest) =>
  request.journey !== 'student_team' || joiningGroup(request)
    ? []
    : request.payload.teammates.flatMap((student, index) =>
        isBlankStudent({ ...student, emailConfirm: '' }) ? [] : [index],
      )

const journeyPrefix: Record<RegistrationIntakeJourney, string> = {
  student_individual: 'studentIndividual',
  student_team: 'studentTeam',
  supervisor_individual: 'supervisorIndividual',
  supervisor_group: 'supervisorGroup',
  supervisor_csv: 'supervisorCsv',
  mentor: 'mentor',
}

export const registrationFormPath = (request: RegistrationRequest, path: string) => {
  const student = /^students\.(\d+)(.*)$/.exec(path)
  if (student) {
    const prefix = studentRequestPrefixes(request)[Number(student[1])]
    return prefix ? `${prefix}${student[2]}` : path
  }
  if (path === 'group.interests') return `${journeyPrefix[request.journey]}.interests`
  if (path === 'group.joinCode') return 'studentTeam.joinCode'
  if (path.startsWith('supervisor.')) {
    return `${journeyPrefix[request.journey]}.${path}`
  }
  if (path === 'source.rowNumbers') return 'supervisorCsv.file'
  return path
}

export const buildProductionRegistrationRequest = (
  request: RegistrationRequest,
  overrideFlags: Record<string, boolean> = {},
) => {
  if (request.journey === 'mentor') {
    return { journey: request.journey, payload: { mentor: request.payload.mentor } }
  }
  const students: SubmittedStudent[] = (() => {
    switch (request.journey) {
      case 'student_individual':
        return [request.payload.student]
      case 'student_team':
        // Member 1's own Areas of Interest go with them; the group's are its own.
        // Joining a group registers only them; teammates left empty aren't.
        return [
          request.payload.creator,
          ...registeredTeammates(request).map((index) => request.payload.teammates[index]!),
        ]
      case 'supervisor_individual':
        return [
          { ...request.payload.student, groupingPreference: request.payload.groupingPreference },
        ]
      case 'supervisor_group':
        return request.payload.students
      case 'supervisor_csv':
        return request.payload.rows.map(({ values }) => {
          const { emailConfirm: _confirmation, ...defaults } = createStudent({
            deferGuardian: true,
          })
          void _confirmation
          const guardian = {
            firstName: values.guardian_first_name,
            lastName: values.guardian_last_name,
            email: values.guardian_email,
            phone: '',
            relationship:
              values.guardian_relationship as StudentDetails['guardian']['relationship'],
            relationshipOther: values.guardian_relationship_other,
          }
          return {
            ...defaults,
            firstName: values.first_name,
            lastName: values.last_name,
            email: values.email,
            school: values.school,
            yearLevel: values.year_level as StudentDetails['yearLevel'],
            country: values.country,
            state: values.state,
            interests: parseRegistrationInterests(values.interests),
            guardian,
            guardianDeferred: !guardian.firstName || !guardian.lastName || !guardian.email,
            groupingPreference: values.grouping_preference,
          }
        })
    }
  })().map((student) => ({
    ...student,
    guardian: student.guardianDeferred ? createStudent().guardian : student.guardian,
    overrides: {},
  }))
  for (const [path, flag] of Object.entries(overrideFlags)) {
    const match =
      /^students\.(\d+)\.overrides\.(ConfirmSchoolOverride|ConfirmNameEmailOverride)$/.exec(path)
    const student = match ? students[Number(match[1])] : undefined
    if (!match || !student || typeof flag !== 'boolean')
      throw new Error('Invalid registration warning override.')
    student.overrides = { ...student.overrides, [match[2]!]: flag }
  }
  const source =
    request.journey === 'supervisor_csv'
      ? {
          method: request.journey,
          fileName: request.payload.fileName,
          rowNumbers: request.payload.rows.map((row) => row.rowNumber),
        }
      : { method: request.journey }
  const supervisor =
    request.journey === 'student_individual' || request.journey === 'student_team'
      ? // Only a supervisor that was given (it's optional), and none when
        // joining a group (it has its own).
        hasSupervisor(request.payload.supervisor) && !joiningGroup(request)
        ? { supervisor: request.payload.supervisor }
        : {}
      : {}
  // A student group takes the code held for it (groupCode.ts), when it has one.
  const codeToken =
    request.journey === 'student_team' && request.payload.groupCodeToken
      ? { codeToken: request.payload.groupCodeToken }
      : {}
  const group =
    request.journey === 'student_team' && joiningGroup(request)
      ? { group: { joinCode: request.payload.joinCode.trim() } }
      : request.journey === 'student_team'
        ? // No shared interests: each member's own go with them.
          { group: { ...codeToken } }
        : request.journey === 'supervisor_group'
          ? { group: { interests: request.payload.interests } }
          : {}
  return { journey: request.journey, payload: { students, source, ...supervisor, ...group } }
}
