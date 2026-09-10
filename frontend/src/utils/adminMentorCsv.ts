import { parseInterestList, type CsvTemplate, type ImportRowError } from './adminStudentCsv'

export interface MentorImportRow {
  firstName: string
  lastName: string
  email: string
  country: string
  /** Sub-national region; null unless the export carries one. */
  state: string | null
  interests: string[]
  mentorReason: string
  mentorInstitution: string
  mentorBackground: string | null
  mentorMaxGroupCount: number
  /** Set when the raw Background value could not be mapped to the backend enum. */
  backgroundNote?: string
}

const MENTOR_HEADER_ALIASES: Record<string, string> = {
  'email address': 'email',
  email: 'email',
  'first name': 'firstName',
  firstname: 'firstName',
  surname: 'lastName',
  'last name': 'lastName',
  lastname: 'lastName',
  country: 'country',
  region: 'region',
  state: 'region',
  'mentor reason': 'mentorReason',
  capacity: 'capacity',
  'max group count': 'capacity',
  'area(s) of interest': 'interests',
  'areas of interest': 'interests',
  interests: 'interests',
  background: 'background',
  'institution or company': 'institution',
  institution: 'institution'
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const normalizeHeader = (header: string) => header.trim().toLowerCase().replace(/\s+/g, ' ')

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

function mapMentorBackground(raw: string): string | null {
  const value = raw.trim().toLowerCase()
  if (!value) return null
  if (value === 'industry') return 'industry'
  if (value.includes('undergraduate')) return 'undergraduate'
  if (value.includes('postgraduate')) return 'postgraduate'
  if (value.includes('hdr')) return 'hdr'
  return null
}

export function parseMentorCsv(text: string): {
  valid: MentorImportRow[]
  invalid: ImportRowError[]
} {
  const rows = parseCsvRows(text)
  if (!rows.length) {
    throw new Error('The CSV file is empty.')
  }

  const [headerRow, ...dataRows] = rows
  const colIndex: Record<string, number> = {}
  headerRow.forEach((header, index) => {
    const canonical = MENTOR_HEADER_ALIASES[normalizeHeader(header)]
    if (canonical && colIndex[canonical] === undefined) {
      colIndex[canonical] = index
    }
  })

  const required: Array<[string, string]> = [
    ['email', 'Email Address'],
    ['firstName', 'First Name'],
    ['lastName', 'Surname'],
    ['country', 'Country'],
    ['interests', 'Area(s) of Interest'],
    ['mentorReason', 'Mentor Reason'],
    ['institution', 'Institution or Company'],
    ['capacity', 'Capacity']
  ]
  const missing = required
    .filter(([key]) => colIndex[key] === undefined)
    .map(([, label]) => label)
  if (missing.length) {
    throw new Error(
      `This doesn't look like a Mentors export - missing columns: ${missing.join(', ')}.`
    )
  }

  const cell = (row: string[], key: string) =>
    colIndex[key] !== undefined ? (row[colIndex[key]] ?? '').trim() : ''

  const valid: MentorImportRow[] = []
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
      const interests = parseInterestList(cell(row, 'interests'))
      const mentorReason = cell(row, 'mentorReason')
      const institution = cell(row, 'institution')
      const capacityRaw = cell(row, 'capacity')
      const backgroundRaw = cell(row, 'background')
      const state = region && region !== country ? region : null
      const capacity = Number(capacityRaw)

      const problems: string[] = []
      if (!email) problems.push('missing email')
      else if (!EMAIL_PATTERN.test(email)) problems.push('invalid email')
      if (!firstName || !lastName) problems.push('missing first or last name')
      if (!country) problems.push('missing country')
      if (!interests.length) problems.push('no interests')
      if (!mentorReason) problems.push('missing mentor reason')
      if (!institution) problems.push('missing institution')
      if (!capacityRaw || !Number.isFinite(capacity) || capacity <= 0) {
        problems.push('invalid capacity')
      }

      if (problems.length) {
        invalid.push({
          rowNumber,
          email: email || '(no email)',
          reason: problems.join(', ')
        })
        return
      }

      const mentorBackground = mapMentorBackground(backgroundRaw)
      valid.push({
        firstName,
        lastName,
        email,
        country,
        state,
        interests,
        mentorReason,
        mentorInstitution: institution,
        mentorBackground,
        mentorMaxGroupCount: capacity,
        backgroundNote:
          backgroundRaw && !mentorBackground
            ? `background "${backgroundRaw}" not recognised - left unset`
            : undefined
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

export const MENTOR_CSV_TEMPLATE = buildCsvTemplate(
  'mentor-import-template.csv',
  MENTOR_HEADER_ALIASES,
  [
    ['email', 'Email Address', 'm.somerville@example.edu'],
    ['firstName', 'First Name', 'Mary'],
    ['lastName', 'Surname', 'Somerville'],
    ['country', 'Country', 'Australia'],
    ['region', 'Region', 'NSW'],
    ['mentorReason', 'Mentor Reason', 'I want to support students exploring biotech careers.'],
    ['capacity', 'Capacity', '2'],
    ['interests', 'Area(s) of Interest', 'Genetics, Bioinformatics'],
    ['background', 'Background', 'Postgraduate'],
    ['institution', 'Institution or Company', 'University of Sydney']
  ]
)
