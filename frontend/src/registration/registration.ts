export const REGISTRATION_JOURNEYS = [
  'student_individual',
  'student_team',
  'supervisor_individual',
  'supervisor_group',
  'supervisor_csv',
  'mentor',
] as const

export type RegistrationJourney = (typeof REGISTRATION_JOURNEYS)[number]
export type RegistrationIntakeJourney = RegistrationJourney

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

export const MAX_CSV_ROWS = 500

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

/** A student's nominated supervisor (a teacher or school supervisor). */
export interface SupervisorDetails {
  firstName: string
  lastName: string
  email: string
}

export interface StudentIndividualForm {
  student: StudentDetails
  supervisor: SupervisorDetails
}

export interface StudentTeamForm {
  creator: StudentDetails
  teammates: StudentDetails[]
  interests: string[]
  supervisor: SupervisorDetails
}

export interface SupervisorIndividualForm {
  student: StudentDetails
  groupingPreference: '' | 'school_only' | 'cross_school'
  /** Students added with Add student: with ``student``, registered as one
   *  group (sent as a supervisor's group). */
  extraStudents: StudentDetails[]
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
  fieldErrors?: Partial<Record<CsvHeader, string>>
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
  /** How they would mentor BIOTech groups. */
  mentoringApproach: string
  /** When they could meet a group each week (optional). */
  availability: AvailabilitySlot[]
}

/** One weekly time a mentor is free: ``weekday`` as the admin pages' mentor
 *  availability counts it (Monday is "0"), times as "HH:MM". */
export interface AvailabilitySlot {
  weekday: string
  start: string
  end: string
}

export const WEEKDAY_NAMES = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

export const createAvailabilitySlot = (): AvailabilitySlot => ({ weekday: '', start: '', end: '' })

/** The most words a mentor's written answers may have. */
export const MENTOR_MAX_WORDS = 150

export const countWords = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0)

export interface RegistrationForms {
  studentIndividual: StudentIndividualForm
  studentTeam: StudentTeamForm
  supervisorIndividual: SupervisorIndividualForm
  supervisorGroup: SupervisorGroupForm
  supervisorCsv: SupervisorCsvForm
  mentor: MentorForm
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

export const isAustralia = (country: string) => country.trim().toLowerCase() === 'australia'

/** The location field after Country: Australia's State (required, from the
 *  database's states), else a Region (optional, typed in). */
export const stateLabel = (country: string) => (isAustralia(country) ? 'State' : 'Region')

export const createStudent = (options: { deferGuardian?: boolean } = {}): StudentDetails => ({
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

/** Whether any of a (optional) nominated supervisor's details were given. */
export const hasSupervisor = (supervisor: SupervisorDetails) =>
  Boolean(supervisor.firstName.trim() || supervisor.lastName.trim() || supervisor.email.trim())

/** A nominated supervisor on Review: their name and email, or none. */
export const supervisorSummary = (supervisor: SupervisorDetails) =>
  hasSupervisor(supervisor)
    ? `${supervisor.firstName} ${supervisor.lastName} · ${supervisor.email}`.trim()
    : ''

export const createSupervisor = (): SupervisorDetails => ({
  firstName: '',
  lastName: '',
  email: '',
})

// A group member: their own details as Member 1's (Australia to start),
// with their guardian's contact optional.
export const createPendingPeer = (): StudentDetails => createStudent({ deferGuardian: true })

export const parseRegistrationInterests = (value: string): string[] =>
  value
    .split(/[,;|]/)
    .map((interest) => interest.trim())
    .filter(Boolean)

export const createRegistrationForms = (): RegistrationForms => ({
  studentIndividual: {
    student: createStudent(),
    supervisor: createSupervisor(),
  },
  studentTeam: {
    creator: createStudent(),
    teammates: [createPendingPeer()],
    interests: [],
    supervisor: createSupervisor(),
  },
  supervisorIndividual: {
    student: createStudent({ deferGuardian: true }),
    groupingPreference: '',
    extraStudents: [],
  },
  supervisorGroup: {
    students: [createStudent({ deferGuardian: true }), createStudent({ deferGuardian: true })],
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
    mentoringApproach: '',
    availability: [createAvailabilitySlot()],
  },
})

const parseCsvMatrix = (text: string) => {
  const rows: Array<{ cells: string[]; rowNumber: number }> = []
  let row: string[] = []
  let value = ''
  let quoted = false
  let lineNumber = 1
  let rowNumber = 1

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
        if (character === '\n') lineNumber += 1
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
      rows.push({ cells: row, rowNumber })
      row = []
      value = ''
      lineNumber += 1
      rowNumber = lineNumber
    } else {
      value += character
    }
  }

  if (quoted) throw new Error('The CSV contains an unclosed quoted value.')
  if (value.length || row.length) {
    row.push(value.replace(/\r$/, ''))
    rows.push({ cells: row, rowNumber })
  }

  return rows.filter(({ cells }) => cells.some((cell) => cell.trim()))
}

const csvRowCategory = (
  values: Record<CsvHeader, string>,
  duplicateEmail: boolean,
  guardianIsStudent: boolean,
): Pick<CsvRow, 'category' | 'issues' | 'fieldErrors'> => {
  const fieldErrors: Partial<Record<CsvHeader, string>> = {}
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
    if (!values[key]) fieldErrors[key] = message
  })

  if (values.email && !isValidRegistrationEmail(values.email)) {
    fieldErrors.email = 'Student email format is invalid.'
  }
  if (duplicateEmail) fieldErrors.email = 'Student email appears more than once in this file.'
  if (values.year_level && !['9', '10', '11', '12'].includes(values.year_level)) {
    fieldErrors.year_level = 'Year level must be 9, 10, 11, or 12.'
  }
  if (values.country.toLowerCase() === 'australia' && !values.state) {
    fieldErrors.state = 'State or territory is required for Australian students.'
  }
  if (values.guardian_email && !isValidRegistrationEmail(values.guardian_email)) {
    fieldErrors.guardian_email = 'Guardian email format is invalid.'
  }
  if (guardianIsStudent)
    fieldErrors.guardian_email = 'A student in this import cannot be listed as a guardian.'
  if (
    values.grouping_preference &&
    !['school_only', 'cross_school'].includes(values.grouping_preference)
  ) {
    fieldErrors.grouping_preference = 'Grouping preference must be school_only or cross_school.'
  }
  if (
    values.guardian_relationship &&
    !['Parent', 'Legal guardian', 'Other'].includes(values.guardian_relationship)
  ) {
    fieldErrors.guardian_relationship = 'Guardian relationship is not recognised.'
  }
  if (values.guardian_relationship === 'Other' && !values.guardian_relationship_other) {
    fieldErrors.guardian_relationship_other = 'Describe the Other guardian relationship.'
  }

  const selectedInterests = parseRegistrationInterests(values.interests)
  if (!selectedInterests.length) fieldErrors.interests = 'At least one interest is required.'
  const unknownInterests = selectedInterests.filter(
    (interest) => !INTEREST_CATEGORIES.includes(interest as (typeof INTEREST_CATEGORIES)[number]),
  )
  if (unknownInterests.length) {
    reviewIssues.push(`Interest needs review: ${unknownInterests.join(', ')}.`)
  }

  // A guardian is their name and email; a relationship, if given, is checked above.
  const guardianCore = [values.guardian_first_name, values.guardian_last_name, values.guardian_email]
  if (guardianCore.every((entry) => !entry)) {
    reviewIssues.push('Guardian details are deferred; student follow-up will be required.')
  } else if (guardianCore.some((entry) => !entry)) {
    reviewIssues.push('Guardian details are incomplete.')
  }

  const blockingIssues = Object.values(fieldErrors)
  if (blockingIssues.length) return { category: 'invalid', issues: blockingIssues, fieldErrors }
  if (reviewIssues.length) return { category: 'review-required', issues: reviewIssues, fieldErrors }
  return { category: 'valid', issues: [], fieldErrors }
}

export const revalidateRegistrationCsvRows = (
  rows: CsvRow[],
  excludedRowNumbers: readonly number[] = [],
): CsvRow[] => {
  const excluded = new Set(excludedRowNumbers)
  const emailCounts = new Map<string, number>()
  for (const row of rows) {
    if (excluded.has(row.rowNumber)) continue
    const email = (row.values.email || '').trim().toLowerCase()
    if (email) emailCounts.set(email, (emailCounts.get(email) || 0) + 1)
  }
  return rows.map((row) => {
    const normalized = { ...row.values }
    for (const header of CSV_HEADERS) normalized[header] = (normalized[header] || '').trim()
    return {
      ...row,
      ...csvRowCategory(
        normalized,
        !excluded.has(row.rowNumber) && (emailCounts.get(normalized.email.toLowerCase()) || 0) > 1,
        emailCounts.has(normalized.guardian_email.toLowerCase()),
      ),
    }
  })
}

export const parseRegistrationCsv = (text: string): CsvParseResult => {
  let matrix: ReturnType<typeof parseCsvMatrix>
  try {
    matrix = parseCsvMatrix(text.replace(/^\uFEFF/, ''))
  } catch (error) {
    return {
      rows: [],
      errors: [error instanceof Error ? error.message : 'The CSV could not be read.'],
    }
  }

  if (!matrix.length) return { rows: [], errors: ['The CSV is empty.'] }
  if (matrix.length - 1 > MAX_CSV_ROWS) {
    return { rows: [], errors: [`Upload no more than ${MAX_CSV_ROWS} students per CSV.`] }
  }

  const headers = matrix[0].cells.map((header) => header.trim())
  const missing = CSV_HEADERS.filter((header) => !headers.includes(header))
  const duplicate = CSV_HEADERS.filter(
    (header) => headers.filter((candidate) => candidate === header).length > 1,
  )
  const unexpected = headers.filter((header) => !CSV_HEADERS.includes(header as CsvHeader))
  const errors: string[] = []
  if (missing.length) errors.push(`Missing columns: ${missing.join(', ')}.`)
  if (duplicate.length) errors.push(`Duplicate columns: ${duplicate.join(', ')}.`)
  if (unexpected.length) errors.push(`Unexpected columns: ${unexpected.join(', ')}.`)
  if (errors.length) return { rows: [], errors }

  const rows: CsvRow[] = matrix.slice(1).map(({ cells, rowNumber }) => {
    const values = Object.fromEntries(
      CSV_HEADERS.map((header) => [header, (cells[headers.indexOf(header)] || '').trim()]),
    ) as Record<CsvHeader, string>
    return {
      rowNumber,
      values,
      category: 'valid',
      issues: [],
    }
  })

  return {
    rows: revalidateRegistrationCsvRows(rows),
    errors: rows.length ? [] : ['The CSV has a header row but no student rows.'],
  }
}

export const registrationCsvTemplate = (): string => `${CSV_HEADERS.join(',')}\r\n`

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
      { label: 'Group creator', email: forms.studentTeam.creator.email },
      ...forms.studentTeam.teammates.map((student, index) => ({
        label: `Member ${index + 2}`,
        email: student.email,
      })),
    ]
  }
  if (journey === 'supervisor_individual') {
    const extra = forms.supervisorIndividual.extraStudents
    if (!extra.length) return [{ label: 'Student', email: forms.supervisorIndividual.student.email }]
    return [forms.supervisorIndividual.student, ...extra].map((student, index) => ({
      label: `Student ${index + 1}`,
      email: student.email,
    }))
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
      ...forms.studentTeam.teammates.map((student, index) => ({
        label: `Member ${index + 2} guardian`,
        email: student.guardianDeferred ? '' : student.guardian.email,
      })),
    ]
  }
  if (journey === 'supervisor_individual') {
    const extra = forms.supervisorIndividual.extraStudents
    if (!extra.length)
      return [{ label: 'Guardian', email: forms.supervisorIndividual.student.guardian.email }]
    return [forms.supervisorIndividual.student, ...extra].map((student, index) => ({
      label: `Student ${index + 1} guardian`,
      email: student.guardian.email,
    }))
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
  }
}

export const sanitizeRegistrationPayload = (value: unknown, key = ''): unknown => {
  if (Array.isArray(value)) return value.map((item) => sanitizeRegistrationPayload(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([entryKey, entryValue]) => {
          if (['emailConfirm', 'previewUrl', 'file'].includes(entryKey)) return false
          return !(typeof File !== 'undefined' && entryValue instanceof File)
        })
        .map(([entryKey, entryValue]) => [
          entryKey,
          sanitizeRegistrationPayload(entryValue, entryKey),
        ]),
    )
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return key.toLowerCase().includes('email') ? trimmed.toLowerCase() : trimmed
  }
  return value
}
