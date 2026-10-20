export const REGISTRATION_JOURNEYS = [
  'student_individual',
  'student_team',
  'supervisor_individual',
  'supervisor_group',
  'supervisor_csv',
  'mentor',
  'supervisor',
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

// Upload student details's columns, in this order (see parseRegistrationCsv).
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
] as const


export const MAX_CSV_ROWS = 1000

export type CsvHeader = (typeof CSV_HEADERS)[number]
export type CsvCategory = 'valid' | 'review-required' | 'invalid'

// Each column as the template and the upload page name it, for the
// supervisors filling it in. An upload may also use the names templates had
// before (first_name), in any case (see parseRegistrationCsv).
export const CSV_HEADER_LABELS: Record<CsvHeader, string> = {
  first_name: 'First Name',
  last_name: 'Last Name',
  email: 'Email',
  school: 'School',
  year_level: 'Year Level',
  country: 'Country',
  state: 'State',
  interests: 'Area(s) of Interest',
  guardian_first_name: 'Guardian First Name',
  guardian_last_name: 'Guardian Last Name',
  guardian_email: 'Guardian Email',
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
  supervisor: SupervisorDetails
  /** The group's code (6 digits, apart from its name), held for it while registering, and the
   *  token the group takes it by. Empty until held (or if it couldn't be). */
  groupCode: string
  groupCodeToken: string
  /** When its hold ends (ISO): a new code is held after that. */
  groupCodeExpiresAt: string
  /** A registered group's code, to join it instead of creating one. */
  joinCode: string
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
  /** The template's example rows, left out (their row numbers). */
  examples: number[]
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
  motivation: string
  /** Asked of a University of Sydney student (see isUsyd) on Affiliation:
   *  whether they study Engineering there, and if so their student ID. */
  usydEngineering: '' | 'yes' | 'no'
  studentId: string
  /** Asked in Australia alone, on their own step before Review: date of
   *  birth (YYYY-MM-DD), their state's Working with Children Check (see
   *  wwccFor), whether they identify as Aboriginal or Torres Strait Islander,
   *  and the languages they speak (with Other's typed in). */
  dateOfBirth: string
  wwccNumber: string
  indigenous: '' | 'yes' | 'no' | 'prefer_not'
  languages: string[]
  languagesOther: string
  /** Drawn on Review, as a PNG data URL: signed again whenever they come back to it. */
  signature: string
}

/** Those asked whether they study Engineering at USYD: its students. */
export const UNIVERSITY_STUDENTS: MentorForm['affiliation'][] = ['undergraduate', 'postgraduate', 'hdr']

// The University of Sydney as it may be typed: lower case, without "the" or
// punctuation. Not Western Sydney University, nor UTS. As the backend's
// (apps.users.mentor_registration.is_usyd).
const USYD_NAMES = ['university of sydney', 'sydney university', 'sydney uni', 'uni of sydney', 'usyd']

export const isUsyd = (institution: string) => {
  const name = institution
    .toLowerCase()
    .replace(/[^a-z ]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ')
    .replace(/^the /, '')
  return USYD_NAMES.includes(name) || name.startsWith('university of sydney ')
}

/** Languages Spoken's choices, as the backend takes them; Other's is typed in. */
export const LANGUAGE_OTHER = 'Other (please specify)'
export const LANGUAGE_OPTIONS = [
  'Arabic',
  'Bengali',
  'English',
  'French',
  'German',
  'Hindi/Urdu',
  'Italian',
  'Japanese',
  'Mandarin',
  'Portuguese',
  'Punjabi',
  'Russian',
  'Spanish',
  LANGUAGE_OTHER,
] as const

export type WorkingWithChildrenCheck = { label: string; check: string; url: string }

// Each state's check, by its code or full name, as the state dropdown may list it.
const WWCC_BY_STATE: Record<string, WorkingWithChildrenCheck> = {
  nsw: {
    label: 'Working with Children Check Number (NSW)',
    check: 'A valid volunteer level WWCC',
    url: 'https://www.service.nsw.gov.au/transaction/apply-for-a-working-with-children-check',
  },
  vic: {
    label: 'Working with Children Check Number (VIC)',
    check: 'A valid volunteer level WWCC',
    url: 'https://www.vic.gov.au/working-with-children-check',
  },
  qld: {
    label: 'Blue Card (QLD)',
    check: 'A valid volunteer Blue Card',
    url: 'https://www.qld.gov.au/bluecard',
  },
  wa: {
    label: 'Working with Children Check Number (WA)',
    check: 'A valid volunteer level WWCC',
    url: 'https://www.wa.gov.au/organisation/department-of-communities/working-children-check',
  },
  sa: {
    label: 'Working with Children Check Number (SA)',
    check: 'A valid volunteer Working with Children Check (WWCC)',
    url: 'https://www.sa.gov.au/topics/rights-and-law/rights-and-responsibilities/screening-checks',
  },
  tas: {
    label: 'Working with Vulnerable People Number (TAS)',
    check: 'A valid volunteer Registration to Work with Vulnerable People (RWVP)',
    url: 'https://www.cbos.tas.gov.au/topics/licensing-and-registration/work-with-vulnerable-people/applications/apply',
  },
  act: {
    label: 'Working with Vulnerable People Number (ACT)',
    check: 'A valid volunteer Working with Vulnerable People (WWVP) registration',
    url: 'https://www.accesscanberra.act.gov.au/business-and-work/working-with-vulnerable-people/apply-for-or-renew-a-wwvp-registration',
  },
  nt: {
    label: 'Ochre Card Number (NT)',
    check: 'A valid volunteer Ochre Card',
    url: 'https://nt.gov.au/emergency/child-safety/apply-for-a-working-with-children-clearance',
  },
}
const STATE_CODES: Record<string, string> = {
  'new south wales': 'nsw',
  victoria: 'vic',
  queensland: 'qld',
  'western australia': 'wa',
  'south australia': 'sa',
  tasmania: 'tas',
  'australian capital territory': 'act',
  'northern territory': 'nt',
}

/** The Working with Children Check an Australian state asks for: its
 *  question, what's required and where to apply. A general one with no state. */
export const wwccFor = (state: string): WorkingWithChildrenCheck => {
  const key = state.trim().toLowerCase()
  return (
    WWCC_BY_STATE[STATE_CODES[key] ?? key] ?? {
      label: 'Working with Children Check Number',
      check: 'A valid volunteer Working with Children Check',
      url: '',
    }
  )
}

/** A supervisor registering themselves: who they are and their school. */
export interface SupervisorForm {
  firstName: string
  lastName: string
  email: string
  school: string
  relationship: '' | 'teacher' | 'parent'
  country: string
  state: string
}

/** The most words a mentor's written answer may have. */
export const MENTOR_MAX_WORDS = 150

export const countWords = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0)

export interface RegistrationForms {
  studentIndividual: StudentIndividualForm
  studentTeam: StudentTeamForm
  supervisorIndividual: SupervisorIndividualForm
  supervisorGroup: SupervisorGroupForm
  supervisorCsv: SupervisorCsvForm
  mentor: MentorForm
  supervisor: SupervisorForm
  /** An admin's students' supervisor (Management > Registration): an existing
   *  supervisor's email, if they choose one, on every supervisor journey. */
  adminSupervisorEmail: string
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
// Called State everywhere; it's required in Australia alone (see isAustralia).
export const stateLabel = () => 'State'

export const createStudent = (options: { deferGuardian?: boolean } = {}): StudentDetails => ({
  firstName: '',
  lastName: '',
  email: '',
  emailConfirm: '',
  school: '',
  yearLevel: '',
  // Picked by whoever fills it in: no country is chosen for anyone.
  country: '',
  state: '',
  interests: [],
  guardianDeferred: Boolean(options.deferGuardian),
  guardian: createGuardian(),
})

/** A group member left empty (their country aside, which starts filled in):
 *  not asked for, nor registered. Any of it given, all of it is asked for. */
export const isBlankStudent = (student: StudentDetails) =>
  ![
    student.firstName,
    student.lastName,
    student.email,
    student.school,
    student.yearLevel,
    student.state,
    student.guardian.firstName,
    student.guardian.lastName,
    student.guardian.email,
  ].some((value) => value.trim()) &&
  !student.interests.length

/** Whether any of a nominated supervisor's details were given. */
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

// A group member: their own details as Member 1's, with their guardian's
// contact optional. Their country follows Member 1's (none until Member 1
// picks one; see RegistrationPage).
export const createPendingPeer = (): StudentDetails => createStudent({ deferGuardian: true })

export const parseRegistrationInterests = (value: string): string[] =>
  value
    .split(/[,;|]/)
    .map((interest) => interest.trim())
    .filter(Boolean)

/** The Areas of Interest option ``text`` names, whatever its case; none when it isn't one. */
export const interestOption = (text: string): (typeof INTEREST_CATEGORIES)[number] | undefined =>
  INTEREST_CATEGORIES.find((option) => option.toLowerCase() === text.trim().toLowerCase())

export const createRegistrationForms = (): RegistrationForms => ({
  adminSupervisorEmail: '',
  studentIndividual: {
    student: createStudent(),
    supervisor: createSupervisor(),
  },
  studentTeam: {
    creator: createStudent(),
    teammates: [createPendingPeer()],
    supervisor: createSupervisor(),
    groupCode: '',
    groupCodeToken: '',
    groupCodeExpiresAt: '',
    joinCode: '',
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
    country: '',
    state: '',
    affiliation: '',
    institution: '',
    company: '',
    universityYear: '',
    fieldOfStudy: '',
    interests: [],
    capacity: '',
    motivation: '',
    usydEngineering: '',
    studentId: '',
    dateOfBirth: '',
    wwccNumber: '',
    indigenous: '',
    languages: [],
    languagesOther: '',
    signature: '',
  },
  supervisor: {
    firstName: '',
    lastName: '',
    email: '',
    school: '',
    relationship: '',
    country: '',
    state: '',
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
  // As the student form: a State in Australia, a Region (optional) elsewhere.
  if (isAustralia(values.country) && !values.state) {
    fieldErrors.state = 'Enter the Australian state or territory.'
  }
  if (values.guardian_email && !isValidRegistrationEmail(values.guardian_email)) {
    fieldErrors.guardian_email = 'Guardian email format is invalid.'
  }
  if (guardianIsStudent)
    fieldErrors.guardian_email = 'A student in this import cannot be listed as a guardian.'

  // Optional, but each one of the Areas of Interest options.
  const unknownInterests = parseRegistrationInterests(values.interests).filter(
    (interest) => !interestOption(interest),
  )
  if (unknownInterests.length) {
    fieldErrors.interests = `Not an Area(s) of Interest option: ${unknownInterests.join(', ')}.`
  }

  // A guardian is their name and email.
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
      examples: [],
    }
  }

  if (!matrix.length) return { rows: [], errors: ['The CSV is empty.'], examples: [] }
  if (matrix.length - 1 > MAX_CSV_ROWS) {
    return { rows: [], errors: [`Upload no more than ${MAX_CSV_ROWS} students per CSV.`], examples: [] }
  }

  // The template's headers, in its order: its name for each (or the old one),
  // in any case, spaces or underscores alike. Columns after them are ignored.
  const headers = matrix[0].cells.map((header) => header.trim())
  const errors = CSV_HEADERS.flatMap((header, index) =>
    headerMatches(headers[index] ?? '', header)
      ? []
      : [
          `Column ${index + 1} must be ${CSV_HEADER_LABELS[header]}${headers[index] ? `, not ${headers[index]}` : ''}.`,
        ],
  )
  if (errors.length) return { rows: [], errors, examples: [] }

  const rows: CsvRow[] = matrix
    .slice(1)
    .map(({ cells, rowNumber }) => ({
      rowNumber,
      values: Object.fromEntries(
        CSV_HEADERS.map((header, index) => [header, (cells[index] || '').trim()]),
      ) as Record<CsvHeader, string>,
      category: 'valid' as const,
      issues: [],
    }))
    // A row with something only in the ignored columns is ignored too.
    .filter(({ values }) => Object.values(values).some(Boolean))

  // The template's example row, if it's still there: never registered.
  const examples = rows.filter(isTemplateExample).map(({ rowNumber }) => rowNumber)
  const students = rows.filter((row) => !isTemplateExample(row))
  return {
    rows: revalidateRegistrationCsvRows(students),
    errors: students.length
      ? []
      : [
          examples.length
            ? "The file only has the template's example row. Add a row for each student."
            : 'The CSV has a header row but no student rows.',
        ],
    examples,
  }
}

// A header compared loosely: "First Name", "first name" and "first_name" alike.
const headerKey = (text: string) => text.trim().toLowerCase().replace(/[\s_]+/g, ' ')

const headerMatches = (typed: string, header: CsvHeader) =>
  [CSV_HEADER_LABELS[header], header].some((name) => headerKey(name) === headerKey(typed))

export const registrationCsvTemplate = (): string =>
  `${CSV_HEADERS.map((header) => CSV_HEADER_LABELS[header]).join(',')}\r\n`

/** The template's example row, to show how each column is filled in. Its
 *  addresses are on the reserved .invalid domain, so it's nobody's: uploaded
 *  back, it's left out (isTemplateExample), never registered. */
export const CSV_EXAMPLE_ROW: Record<CsvHeader, string> = {
  first_name: 'Alex',
  last_name: 'Example',
  email: 'alex.example@school.invalid',
  school: 'Example High School',
  year_level: '10',
  country: 'Australia',
  state: 'NSW',
  interests: 'Biomedical Innovations, AI & Robotics and Smart Systems',
  guardian_first_name: 'Pat',
  guardian_last_name: 'Example',
  guardian_email: 'pat.example@family.invalid',
}

/** Beside the example row in the template (a column uploads ignore). */
export const CSV_EXAMPLE_NOTE =
  "Example only: this row won't be registered. Add your students below it, or type over it."

/** The template: its header row, and its example row. */
export const registrationTemplateRows = () => ({
  header: CSV_HEADERS.map((header) => CSV_HEADER_LABELS[header]),
  example: CSV_HEADERS.map((header) => CSV_EXAMPLE_ROW[header]),
})

/** The template's own example row, uploaded back (its student's address). */
export const isTemplateExample = (row: Pick<CsvRow, 'values'>) =>
  row.values.email.trim().toLowerCase() === CSV_EXAMPLE_ROW.email

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
    case 'supervisor':
      return { supervisor: forms.supervisor }
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
