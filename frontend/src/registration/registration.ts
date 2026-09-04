export const REGISTRATION_JOURNEYS = [
  'student_individual',
  'student_team',
  'supervisor_individual',
  'supervisor_group',
  'supervisor_csv',
  'mentor',
  'guardian_consent',
] as const

export type RegistrationJourney = (typeof REGISTRATION_JOURNEYS)[number]
export type RegistrationIntakeJourney = Exclude<RegistrationJourney, 'guardian_consent'>

export const INTEREST_CATEGORIES = [
  'Biomedical Innovations',
  'Environmental Sustainability & Climate Tech',
  'Space & Astrobiology',
  'AI & Robotics and Smart Systems',
  'Nanotechnology & Materials Science',
  'Food & Agriculture Technology',
  'Neuroscience & Mental Health Tech',
  'Water & Energy Tech',
  'Ethical & Societal Impacts of Emerging Tech',
] as const

export const PRONOUN_OPTIONS = [
  'She/her',
  'He/him',
  'They/them',
  'Prefer not to say',
  'Other',
] as const

export const CSV_HEADERS = [
  'first_name',
  'last_name',
  'email',
  'school',
  'year_level',
  'country',
  'state',
  'interests',
  'guardian_first_name',
  'guardian_last_name',
  'guardian_email',
  'guardian_relationship',
  'guardian_relationship_other',
  'grouping_preference',
] as const

export type CsvHeader = (typeof CSV_HEADERS)[number]
export type CsvCategory = 'valid' | 'review-required' | 'invalid'

export interface PhotoMetadata {
  name: string
  type: string
  size: number
}

export interface GuardianDetails {
  firstName: string
  lastName: string
  email: string
  phone: string
  relationship: '' | 'Parent' | 'Legal guardian' | 'Other'
  relationshipOther: string
}

export interface StudentDetails {
  firstName: string
  lastName: string
  email: string
  emailConfirm: string
  school: string
  yearLevel: '' | '9' | '10' | '11' | '12'
  country: string
  state: string
  interests: string[]
  pronouns: string
  pronounsOther: string
  profilePhoto: PhotoMetadata | null
  guardianDeferred: boolean
  guardian: GuardianDetails
}

export interface SupervisorDetails {
  firstName: string
  lastName: string
  email: string
  school: string
}

export interface StudentIndividualForm {
  student: StudentDetails
  supervisorMode: 'school' | 'parent'
  supervisor: SupervisorDetails
}

export interface StudentTeamForm {
  creator: StudentDetails
  teammates: StudentDetails[]
  interests: string[]
  supervisorMode: 'school' | 'parent'
  supervisor: SupervisorDetails
}

export interface SupervisorIndividualForm {
  student: StudentDetails
  groupingPreference: 'school_only' | 'cross_school'
}

export interface SupervisorGroupForm {
  students: StudentDetails[]
  interests: string[]
}

export interface CsvRow {
  rowNumber: number
  values: Record<CsvHeader, string>
  category: CsvCategory
  issues: string[]
}

export interface CsvParseResult {
  rows: CsvRow[]
  errors: string[]
}

export interface SupervisorCsvForm {
  fileName: string
  rows: CsvRow[]
  excludedRowNumbers: number[]
}

export interface MentorForm {
  firstName: string
  lastName: string
  email: string
  phone: string
  country: string
  state: string
  affiliation: '' | 'undergraduate' | 'postgraduate' | 'hdr' | 'academic' | 'industry'
  institution: string
  company: string
  universityYear: string
  fieldOfStudy: string
  interests: string[]
  capacity: '' | '1' | '2' | '3' | '4' | '5'
  background: string
  motivation: string
  indigenousStatus: '' | 'Yes' | 'No' | 'Prefer not to say'
  languages: string
  languagesPreferNot: boolean
  dateOfBirth: string
  dateOfBirthPreferNot: boolean
  safeguardingJurisdiction: string
  safeguardingStatus: 'pending-review'
  complianceDeclaration: boolean
  attestation: boolean
}

export interface GuardianConsentForm {
  invitationReference: string
  studentName: string
  guardianFirstName: string
  guardianLastName: string
  guardianEmail: string
  phone: string
  relationship: '' | 'Parent' | 'Legal guardian' | 'Other'
  relationshipOther: string
  participationAcknowledged: boolean
  mediaConsent: '' | 'yes' | 'no'
  wordingVersion: string
}

export interface RegistrationForms {
  studentIndividual: StudentIndividualForm
  studentTeam: StudentTeamForm
  supervisorIndividual: SupervisorIndividualForm
  supervisorGroup: SupervisorGroupForm
  supervisorCsv: SupervisorCsvForm
  mentor: MentorForm
  guardianConsent: GuardianConsentForm
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const isValidRegistrationEmail = (value: string) => emailPattern.test(value.trim())

export const createGuardian = (): GuardianDetails => ({
  firstName: '',
  lastName: '',
  email: '',
  phone: '',
  relationship: '',
  relationshipOther: '',
})

export const createStudent = (
  options: { deferGuardian?: boolean } = {},
): StudentDetails => ({
  firstName: '',
  lastName: '',
  email: '',
  emailConfirm: '',
  school: '',
  yearLevel: '',
  country: 'Australia',
  state: '',
  interests: [],
  pronouns: '',
  pronounsOther: '',
  profilePhoto: null,
  guardianDeferred: Boolean(options.deferGuardian),
  guardian: createGuardian(),
})

export const createSupervisor = (): SupervisorDetails => ({
  firstName: '',
  lastName: '',
  email: '',
  school: '',
})

export const createRegistrationForms = (): RegistrationForms => ({
  studentIndividual: {
    student: createStudent(),
    supervisorMode: 'school',
    supervisor: createSupervisor(),
  },
  studentTeam: {
    creator: createStudent(),
    teammates: [createStudent({ deferGuardian: true })],
    interests: [],
    supervisorMode: 'school',
    supervisor: createSupervisor(),
  },
  supervisorIndividual: {
    student: createStudent({ deferGuardian: true }),
    groupingPreference: 'school_only',
  },
  supervisorGroup: {
    students: [
      createStudent({ deferGuardian: true }),
      createStudent({ deferGuardian: true }),
    ],
    interests: [],
  },
  supervisorCsv: {
    fileName: '',
    rows: [],
    excludedRowNumbers: [],
  },
  mentor: {
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    country: 'Australia',
    state: '',
    affiliation: '',
    institution: '',
    company: '',
    universityYear: '',
    fieldOfStudy: '',
    interests: [],
    capacity: '',
    background: '',
    motivation: '',
    indigenousStatus: 'Prefer not to say',
    languages: '',
    languagesPreferNot: false,
    dateOfBirth: '',
    dateOfBirthPreferNot: false,
    safeguardingJurisdiction: '',
    safeguardingStatus: 'pending-review',
    complianceDeclaration: false,
    attestation: false,
  },
  guardianConsent: {
    invitationReference: 'BTF-GUARDIAN-DEMO-1042',
    studentName: 'Alex Morgan',
    guardianFirstName: '',
    guardianLastName: '',
    guardianEmail: '',
    phone: '',
    relationship: '',
    relationshipOther: '',
    participationAcknowledged: false,
    mediaConsent: '',
    wordingVersion: 'Preview wording — approval pending',
  },
})

const parseCsvMatrix = (text: string): string[][] => {
  const rows: string[][] = []
  let row: string[] = []
  let value = ''
  let quoted = false

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]

    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        value += '"'
        index += 1
      } else if (character === '"') {
        quoted = false
      } else {
        value += character
      }
      continue
    }

    if (character === '"' && value.length === 0) {
      quoted = true
    } else if (character === ',') {
      row.push(value)
      value = ''
    } else if (character === '\n') {
      row.push(value.replace(/\r$/, ''))
      rows.push(row)
      row = []
      value = ''
    } else {
      value += character
    }
  }

  if (quoted) throw new Error('The CSV contains an unclosed quoted value.')
  if (value.length || row.length) {
    row.push(value.replace(/\r$/, ''))
    rows.push(row)
  }

  return rows.filter((candidate) => candidate.some((cell) => cell.trim()))
}

const csvRowCategory = (
  values: Record<CsvHeader, string>,
  duplicateEmail: boolean,
): Pick<CsvRow, 'category' | 'issues'> => {
  const blockingIssues: string[] = []
  const reviewIssues: string[] = []

  const required: Array<[CsvHeader, string]> = [
    ['first_name', 'First name is required.'],
    ['last_name', 'Last name is required.'],
    ['email', 'Student email is required.'],
    ['school', 'School is required.'],
    ['year_level', 'Year level is required.'],
    ['country', 'Country is required.'],
    ['interests', 'At least one interest is required.'],
  ]

  required.forEach(([key, message]) => {
    if (!values[key]) blockingIssues.push(message)
  })

  if (values.email && !isValidRegistrationEmail(values.email)) {
    blockingIssues.push('Student email format is invalid.')
  }
  if (duplicateEmail) blockingIssues.push('Student email appears more than once in this file.')
  if (values.year_level && !['9', '10', '11', '12'].includes(values.year_level)) {
    blockingIssues.push('Year level must be 9, 10, 11, or 12.')
  }
  if (values.guardian_email && !isValidRegistrationEmail(values.guardian_email)) {
    blockingIssues.push('Guardian email format is invalid.')
  }
  if (
    values.grouping_preference &&
    !['school_only', 'cross_school'].includes(values.grouping_preference)
  ) {
    blockingIssues.push('Grouping preference must be school_only or cross_school.')
  }
  if (
    values.guardian_relationship &&
    !['Parent', 'Legal guardian', 'Other'].includes(values.guardian_relationship)
  ) {
    blockingIssues.push('Guardian relationship is not recognised.')
  }
  if (values.guardian_relationship === 'Other' && !values.guardian_relationship_other) {
    blockingIssues.push('Describe the Other guardian relationship.')
  }

  const selectedInterests = values.interests
    .split('|')
    .map((interest) => interest.trim())
    .filter(Boolean)
  const unknownInterests = selectedInterests.filter(
    (interest) => !INTEREST_CATEGORIES.includes(interest as (typeof INTEREST_CATEGORIES)[number]),
  )
  if (unknownInterests.length) {
    reviewIssues.push(`Interest needs review: ${unknownInterests.join(', ')}.`)
  }

  const guardianCore = [
    values.guardian_first_name,
    values.guardian_last_name,
    values.guardian_email,
    values.guardian_relationship,
  ]
  if (guardianCore.every((entry) => !entry)) {
    reviewIssues.push('Guardian details are deferred; student follow-up will be required.')
  } else if (guardianCore.some((entry) => !entry)) {
    reviewIssues.push('Guardian details are incomplete.')
  }

  if (blockingIssues.length) return { category: 'invalid', issues: blockingIssues }
  if (reviewIssues.length) return { category: 'review-required', issues: reviewIssues }
  return { category: 'valid', issues: [] }
}

export const parseRegistrationCsv = (text: string): CsvParseResult => {
  let matrix: string[][]
  try {
    matrix = parseCsvMatrix(text.replace(/^\uFEFF/, ''))
  } catch (error) {
    return {
      rows: [],
      errors: [error instanceof Error ? error.message : 'The CSV could not be read.'],
    }
  }

  if (!matrix.length) return { rows: [], errors: ['The CSV is empty.'] }

  const headers = matrix[0].map((header) => header.trim())
  const missing = CSV_HEADERS.filter((header) => !headers.includes(header))
  const unexpected = headers.filter((header) => !CSV_HEADERS.includes(header as CsvHeader))
  const errors: string[] = []
  if (missing.length) errors.push(`Missing columns: ${missing.join(', ')}.`)
  if (unexpected.length) errors.push(`Unexpected columns: ${unexpected.join(', ')}.`)
  if (errors.length) return { rows: [], errors }

  const emailCounts = new Map<string, number>()
  matrix.slice(1).forEach((cells) => {
    const emailIndex = headers.indexOf('email')
    const email = (cells[emailIndex] || '').trim().toLowerCase()
    if (email) emailCounts.set(email, (emailCounts.get(email) || 0) + 1)
  })

  const rows = matrix.slice(1).map((cells, index) => {
    const values = Object.fromEntries(
      CSV_HEADERS.map((header) => [header, (cells[headers.indexOf(header)] || '').trim()]),
    ) as Record<CsvHeader, string>
    const normalizedEmail = values.email.toLowerCase()
    const result = csvRowCategory(
      values,
      Boolean(normalizedEmail && emailCounts.get(normalizedEmail)! > 1),
    )
    return {
      rowNumber: index + 2,
      values,
      ...result,
    }
  })

  return {
    rows,
    errors: rows.length ? [] : ['The CSV has a header row but no student rows.'],
  }
}

const csvEscape = (value: string) =>
  /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value

export const registrationCsvTemplate = (): string => {
  const example: Record<CsvHeader, string> = {
    first_name: 'Alex',
    last_name: 'Morgan',
    email: 'alex.morgan@example.edu.au',
    school: 'Example Secondary College',
    year_level: '10',
    country: 'Australia',
    state: 'NSW',
    interests: 'Biomedical Innovations|AI & Robotics and Smart Systems',
    guardian_first_name: 'Taylor',
    guardian_last_name: 'Morgan',
    guardian_email: 'taylor.morgan@example.com',
    guardian_relationship: 'Parent',
    guardian_relationship_other: '',
    grouping_preference: 'school_only',
  }

  return `${CSV_HEADERS.join(',')}\r\n${CSV_HEADERS.map((header) => csvEscape(example[header])).join(',')}\r\n`
}

const normalizedEmail = (value: string) => value.trim().toLowerCase()

const studentEmailsForJourney = (
  journey: RegistrationJourney,
  forms: RegistrationForms,
): Array<{ label: string; email: string }> => {
  if (journey === 'student_individual') {
    return [{ label: 'Student', email: forms.studentIndividual.student.email }]
  }
  if (journey === 'student_team') {
    return [
      { label: 'Team creator', email: forms.studentTeam.creator.email },
      ...forms.studentTeam.teammates.map((student, index) => ({
        label: `Teammate ${index + 1}`,
        email: student.email,
      })),
    ]
  }
  if (journey === 'supervisor_individual') {
    return [{ label: 'Student', email: forms.supervisorIndividual.student.email }]
  }
  if (journey === 'supervisor_group') {
    return forms.supervisorGroup.students.map((student, index) => ({
      label: `Student ${index + 1}`,
      email: student.email,
    }))
  }
  if (journey === 'supervisor_csv') {
    return forms.supervisorCsv.rows
      .filter((row) => !forms.supervisorCsv.excludedRowNumbers.includes(row.rowNumber))
      .map((row) => ({ label: `CSV row ${row.rowNumber}`, email: row.values.email }))
  }
  return []
}

const adultEmailsForJourney = (
  journey: RegistrationJourney,
  forms: RegistrationForms,
): Array<{ label: string; email: string }> => {
  if (journey === 'student_individual') {
    return [
      { label: 'Supervisor', email: forms.studentIndividual.supervisor.email },
      { label: 'Guardian', email: forms.studentIndividual.student.guardian.email },
    ]
  }
  if (journey === 'student_team') {
    return [
      { label: 'Supervisor', email: forms.studentTeam.supervisor.email },
      { label: 'Guardian', email: forms.studentTeam.creator.guardian.email },
    ]
  }
  if (journey === 'supervisor_individual') {
    return [{ label: 'Guardian', email: forms.supervisorIndividual.student.guardian.email }]
  }
  if (journey === 'supervisor_group') {
    return forms.supervisorGroup.students.map((student, index) => ({
      label: `Student ${index + 1} guardian`,
      email: student.guardian.email,
    }))
  }
  if (journey === 'supervisor_csv') {
    return forms.supervisorCsv.rows
      .filter((row) => !forms.supervisorCsv.excludedRowNumbers.includes(row.rowNumber))
      .map((row) => ({
        label: `CSV row ${row.rowNumber} guardian`,
        email: row.values.guardian_email,
      }))
  }
  return []
}

export const findCrossRoleEmailConflicts = (
  journey: RegistrationJourney,
  forms: RegistrationForms,
): string[] => {
  const students = studentEmailsForJourney(journey, forms)
    .map((entry) => ({ ...entry, email: normalizedEmail(entry.email) }))
    .filter((entry) => entry.email)
  const adults = adultEmailsForJourney(journey, forms)
    .map((entry) => ({ ...entry, email: normalizedEmail(entry.email) }))
    .filter((entry) => entry.email)
  const messages: string[] = []

  students.forEach((student, index) => {
    if (students.slice(index + 1).some((candidate) => candidate.email === student.email)) {
      messages.push(`${student.label} email is already used by another student.`)
    }
    const adult = adults.find((candidate) => candidate.email === student.email)
    if (adult)
      messages.push(
        `${student.label} email must be different from the ${adult.label.toLowerCase()} email.`,
      )
  })

  return [...new Set(messages)]
}

export const payloadForRegistrationJourney = (
  journey: RegistrationJourney,
  forms: RegistrationForms,
): unknown => {
  switch (journey) {
    case 'student_individual':
      return forms.studentIndividual
    case 'student_team':
      return forms.studentTeam
    case 'supervisor_individual':
      return forms.supervisorIndividual
    case 'supervisor_group':
      return forms.supervisorGroup
    case 'supervisor_csv':
      return {
        ...forms.supervisorCsv,
        rows: forms.supervisorCsv.rows.filter(
          (row) => !forms.supervisorCsv.excludedRowNumbers.includes(row.rowNumber),
        ),
      }
    case 'mentor':
      return { mentor: forms.mentor }
    case 'guardian_consent':
      return {
        invitation: {
          reference: forms.guardianConsent.invitationReference,
          studentName: forms.guardianConsent.studentName,
          wordingVersion: forms.guardianConsent.wordingVersion,
        },
        guardian: {
          firstName: forms.guardianConsent.guardianFirstName,
          lastName: forms.guardianConsent.guardianLastName,
          email: forms.guardianConsent.guardianEmail,
          phone: forms.guardianConsent.phone,
          relationship: forms.guardianConsent.relationship,
          relationshipOther: forms.guardianConsent.relationshipOther,
        },
        consent: {
          participationAcknowledged: forms.guardianConsent.participationAcknowledged,
          mediaConsent: forms.guardianConsent.mediaConsent,
        },
      }
  }
}

const cleanPayloadValue = (value: unknown, key = ''): unknown => {
  if (Array.isArray(value)) return value.map((item) => cleanPayloadValue(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([entryKey]) => !['emailConfirm', 'previewUrl'].includes(entryKey))
        .map(([entryKey, entryValue]) => [entryKey, cleanPayloadValue(entryValue, entryKey)]),
    )
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return key.toLowerCase().includes('email') ? trimmed.toLowerCase() : trimmed
  }
  return value
}

export const buildRegistrationDemoRequest = (
  journey: RegistrationJourney,
  forms: RegistrationForms,
) => ({
  journey,
  payload: cleanPayloadValue(payloadForRegistrationJourney(journey, forms)),
})

export type RegistrationDemoForms = RegistrationForms

export const createRegistrationDemoForms = createRegistrationForms
