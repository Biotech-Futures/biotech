export interface StudentImportRow {
  firstName: string
  lastName: string
  email: string
  country: string
  /** Sub-national region; null unless the export carries one. */
  state: string | null
  schoolName: string
  yearLevel: number
  interests: string[]
  guardianFirstName: string
  guardianLastName: string
  guardianEmail: string
  supervisorFirstName: string
  supervisorLastName: string
  supervisorEmail: string
  joinpermResponseId: string
  /** False when there is no approval ResponseID. */
  active: boolean
  /** Co-registration: students sharing this value are grouped by the backend. */
  groupNumber?: string
}

export interface ImportRowError {
  rowNumber: number
  email: string
  reason: string
}

export interface CsvTemplate {
  fileName: string
  headers: string[]
  sampleRow: string[]
}

const STUDENT_HEADER_ALIASES: Record<string, string> = {
  'student email address': 'email',
  'email address': 'email',
  email: 'email',
  'first name': 'firstName',
  firstname: 'firstName',
  surname: 'lastName',
  'last name': 'lastName',
  lastname: 'lastName',
  'guardian first name': 'guardianFirstName',
  'guardian surname': 'guardianLastName',
  'guardian last name': 'guardianLastName',
  'guardian email': 'guardianEmail',
  'school name': 'school',
  school: 'school',
  schoolname: 'school',
  'year level': 'yearLevel',
  yearlevel: 'yearLevel',
  'area(s) of interest': 'interests',
  'areas of interest': 'interests',
  interests: 'interests',
  'supervisor first name': 'supervisorFirstName',
  'supervisor surname': 'supervisorLastName',
  'supervisor last name': 'supervisorLastName',
  'supervisor email': 'supervisorEmail',
  'parent/guardian approval responseid': 'responseId',
  'approval responseid': 'responseId',
  responseid: 'responseId',
  country: 'country',
  region: 'region',
  state: 'region',
  'group number': 'groupNumber',
  'group no': 'groupNumber',
  'group no.': 'groupNumber',
  'group #': 'groupNumber',
  'group id': 'groupNumber',
  group: 'groupNumber',
  groupnumber: 'groupNumber'
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const normalizeHeader = (header: string) => header.trim().toLowerCase().replace(/\s+/g, ' ')

export function parseInterestList(input: string): string[] {
  return Array.from(
    new Set(
      input
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    )
  )
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = []
  let currentRow: string[] = []
  let currentCell = ''
  let insideQuotes = false

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]
    const nextChar = text[i + 1]

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentCell += '"'
        i += 1
      } else {
        insideQuotes = !insideQuotes
      }
      continue
    }

    if (char === ',' && !insideQuotes) {
      currentRow.push(currentCell)
      currentCell = ''
      continue
    }

    if ((char === '\n' || char === '\r') && !insideQuotes) {
      if (char === '\r' && nextChar === '\n') i += 1
      currentRow.push(currentCell)
      rows.push(currentRow)
      currentRow = []
      currentCell = ''
      continue
    }

    currentCell += char
  }

  if (currentCell.length || currentRow.length) {
    currentRow.push(currentCell)
    rows.push(currentRow)
  }

  return rows
}

export function parseStudentCsv(text: string): {
  valid: StudentImportRow[]
  invalid: ImportRowError[]
} {
  const rows = parseCsvRows(text)
  if (!rows.length) {
    throw new Error('The CSV file is empty.')
  }

  const [headerRow, ...dataRows] = rows
  const colIndex: Record<string, number> = {}
  headerRow.forEach((header, index) => {
    const canonical = STUDENT_HEADER_ALIASES[normalizeHeader(header)]
    if (canonical && colIndex[canonical] === undefined) {
      colIndex[canonical] = index
    }
  })

  const required: Array<[string, string]> = [
    ['email', 'Student email address'],
    ['firstName', 'First Name'],
    ['lastName', 'Surname'],
    ['country', 'Country'],
    ['school', 'School Name'],
    ['yearLevel', 'Year Level'],
    ['interests', 'Area(s) of Interest']
  ]
  const missing = required
    .filter(([key]) => colIndex[key] === undefined)
    .map(([, label]) => label)
  if (missing.length) {
    throw new Error(
      `This doesn't look like a Students export - missing columns: ${missing.join(', ')}.`
    )
  }

  const cell = (row: string[], key: string) =>
    colIndex[key] !== undefined ? (row[colIndex[key]] ?? '').trim() : ''

  const valid: StudentImportRow[] = []
  const invalid: ImportRowError[] = []

  dataRows
    .filter((row) => row.some((value) => value.trim()))
    .forEach((row, index) => {
      const rowNumber = index + 2
      const email = cell(row, 'email').toLowerCase()
      const firstName = cell(row, 'firstName')
      const lastName = cell(row, 'lastName')
      const country = cell(row, 'country')
      const region = cell(row, 'region')
      const schoolName = cell(row, 'school')
      const yearLevelRaw = cell(row, 'yearLevel')
      const interests = parseInterestList(cell(row, 'interests'))
      const responseId = cell(row, 'responseId')
      const state = region && region !== country ? region : null
      const yearLevel = Number(yearLevelRaw)

      const problems: string[] = []
      if (!email) problems.push('missing email')
      else if (!EMAIL_PATTERN.test(email)) problems.push('invalid email')
      if (!firstName || !lastName) problems.push('missing first or last name')
      if (!country) problems.push('missing country')
      if (!schoolName) problems.push('missing school')
      if (!yearLevelRaw || !Number.isInteger(yearLevel) || yearLevel < 9 || yearLevel > 12) {
        problems.push('year level must be 9-12')
      }
      if (!interests.length) problems.push('no interests')

      if (problems.length) {
        invalid.push({
          rowNumber,
          email: email || '(no email)',
          reason: problems.join(', ')
        })
        return
      }

      valid.push({
        firstName,
        lastName,
        email,
        country,
        state,
        schoolName,
        yearLevel,
        interests,
        guardianFirstName: cell(row, 'guardianFirstName'),
        guardianLastName: cell(row, 'guardianLastName'),
        guardianEmail: cell(row, 'guardianEmail').toLowerCase(),
        supervisorFirstName: cell(row, 'supervisorFirstName'),
        supervisorLastName: cell(row, 'supervisorLastName'),
        supervisorEmail: cell(row, 'supervisorEmail').toLowerCase(),
        joinpermResponseId: responseId,
        active: responseId.length > 0,
        groupNumber: cell(row, 'groupNumber') || undefined
      })
    })

  return { valid, invalid }
}

function templateHeader(
  aliases: Record<string, string>,
  canonical: string,
  preferred: string
): string {
  if (aliases[normalizeHeader(preferred)] === canonical) return preferred
  return Object.keys(aliases).find((alias) => aliases[alias] === canonical) ?? preferred
}

function buildCsvTemplate(
  fileName: string,
  aliases: Record<string, string>,
  columns: Array<[canonical: string, header: string, sample: string]>
): CsvTemplate {
  return {
    fileName,
    headers: columns.map(([canonical, header]) => templateHeader(aliases, canonical, header)),
    sampleRow: columns.map(([, , sample]) => sample)
  }
}

export const STUDENT_CSV_TEMPLATE = buildCsvTemplate(
  'student-import-template.csv',
  STUDENT_HEADER_ALIASES,
  [
    ['email', 'Student email address', 'ada.lovelace@example.edu'],
    ['firstName', 'First Name', 'Ada'],
    ['lastName', 'Surname', 'Lovelace'],
    ['guardianFirstName', 'Guardian First Name', 'Anne'],
    ['guardianLastName', 'Guardian Surname', 'Lovelace'],
    ['guardianEmail', 'Guardian Email', 'anne.lovelace@example.com'],
    ['school', 'School Name', 'Sydney Girls High School'],
    ['yearLevel', 'Year Level', '11'],
    ['interests', 'Area(s) of Interest', 'Genetics, Bioinformatics'],
    ['supervisorFirstName', 'Supervisor First Name', 'Mary'],
    ['supervisorLastName', 'Supervisor Surname', 'Somerville'],
    ['supervisorEmail', 'Supervisor Email', 'm.somerville@example.edu'],
    ['responseId', 'Parent/Guardian Approval ResponseID', 'R_1a2b3c4d5e6f7g8'],
    ['country', 'Country', 'Australia'],
    ['region', 'Region', 'NSW'],
    ['groupNumber', 'Group Number', '1']
  ]
)
