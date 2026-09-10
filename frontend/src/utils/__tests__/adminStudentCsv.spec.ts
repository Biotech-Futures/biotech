import { describe, expect, it } from 'vitest'
import {
  parseInterestList,
  parseStudentCsv,
  STUDENT_CSV_TEMPLATE
} from '@/utils/adminStudentCsv'

const header = [
  'Student email address',
  'First Name',
  'Surname',
  'Guardian First Name',
  'Guardian Surname',
  'Guardian Email',
  'School Name',
  'Year Level',
  'Area(s) of Interest',
  'Supervisor First Name',
  'Supervisor Surname',
  'Supervisor Email',
  'Parent/Guardian Approval ResponseID',
  'Country',
  'Region',
  'Group Number'
].join(',')

describe('parseInterestList', () => {
  it('trims, removes blanks, and deduplicates interests', () => {
    expect(parseInterestList('Genetics, Bioinformatics, Genetics, , Microbiology')).toEqual([
      'Genetics',
      'Bioinformatics',
      'Microbiology'
    ])
  })
})

describe('parseStudentCsv', () => {
  it('parses a valid student registration export row', () => {
    const csv = [
      header,
      [
        'ADA.LOVELACE@EXAMPLE.EDU',
        'Ada',
        'Lovelace',
        'Anne',
        'Lovelace',
        'ANNE.LOVELACE@EXAMPLE.COM',
        'Sydney Girls High School',
        '11',
        '"Genetics, Bioinformatics, Genetics"',
        'Mary',
        'Somerville',
        'M.SOMERVILLE@EXAMPLE.EDU',
        'R_1a2b3c4d5e6f7g8',
        'Australia',
        'NSW',
        '1'
      ].join(',')
    ].join('\n')

    const result = parseStudentCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid).toEqual([
      {
        firstName: 'Ada',
        lastName: 'Lovelace',
        email: 'ada.lovelace@example.edu',
        country: 'Australia',
        state: 'NSW',
        schoolName: 'Sydney Girls High School',
        yearLevel: 11,
        interests: ['Genetics', 'Bioinformatics'],
        guardianFirstName: 'Anne',
        guardianLastName: 'Lovelace',
        guardianEmail: 'anne.lovelace@example.com',
        supervisorFirstName: 'Mary',
        supervisorLastName: 'Somerville',
        supervisorEmail: 'm.somerville@example.edu',
        joinpermResponseId: 'R_1a2b3c4d5e6f7g8',
        active: true,
        groupNumber: '1'
      }
    ])
  })

  it('accepts supported aliases for required and optional columns', () => {
    const csv = [
      'email,firstname,lastname,country,school,yearlevel,interests,state,group',
      'grace@example.edu,Grace,Hopper,Australia,State High,10,"Robotics, AI",VIC,7'
    ].join('\n')

    const result = parseStudentCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid[0]).toMatchObject({
      firstName: 'Grace',
      lastName: 'Hopper',
      email: 'grace@example.edu',
      country: 'Australia',
      state: 'VIC',
      schoolName: 'State High',
      yearLevel: 10,
      interests: ['Robotics', 'AI'],
      active: false,
      groupNumber: '7'
    })
  })

  it('treats blank rows as absent and reports row-level validation problems', () => {
    const csv = [
      header,
      '',
      ',Missing,Email,,,,State High,8,,,,,,Australia,NSW,',
      'not-an-email,Ada,Lovelace,,,,State High,12,Genetics,,,,,Australia,NSW,',
      'valid@example.edu,Valid,Student,,,,State High,9,Genetics,,,,,Australia,NSW,'
    ].join('\n')

    const result = parseStudentCsv(csv)

    expect(result.valid).toHaveLength(1)
    expect(result.valid[0].email).toBe('valid@example.edu')
    expect(result.invalid).toEqual([
      {
        rowNumber: 2,
        email: '(no email)',
        reason: 'missing email, year level must be 9-12, no interests'
      },
      {
        rowNumber: 3,
        email: 'not-an-email',
        reason: 'invalid email'
      }
    ])
  })

  it('uses null state when Region is blank or equal to Country', () => {
    const csv = [
      'Student email address,First Name,Surname,Country,Region,School Name,Year Level,Area(s) of Interest',
      'country-as-region@example.edu,Case,One,Australia,Australia,State High,10,Genetics',
      'blank-region@example.edu,Case,Two,New Zealand,,Wellington High,11,Bioinformatics'
    ].join('\n')

    const result = parseStudentCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid.map((row) => row.state)).toEqual([null, null])
  })

  it('throws a file-level error for an empty CSV', () => {
    expect(() => parseStudentCsv('')).toThrow('The CSV file is empty.')
  })

  it('throws a file-level error when required columns are missing', () => {
    expect(() => parseStudentCsv('Email,First Name\nada@example.edu,Ada')).toThrow(
      "This doesn't look like a Students export - missing columns: Surname, Country, School Name, Year Level, Area(s) of Interest."
    )
  })

  it('exports the student CSV template with parser-compatible headers', () => {
    expect(STUDENT_CSV_TEMPLATE.fileName).toBe('student-import-template.csv')
    expect(STUDENT_CSV_TEMPLATE.headers).toEqual([
      'Student email address',
      'First Name',
      'Surname',
      'Guardian First Name',
      'Guardian Surname',
      'Guardian Email',
      'School Name',
      'Year Level',
      'Area(s) of Interest',
      'Supervisor First Name',
      'Supervisor Surname',
      'Supervisor Email',
      'Parent/Guardian Approval ResponseID',
      'Country',
      'Region',
      'Group Number'
    ])
    expect(STUDENT_CSV_TEMPLATE.sampleRow).toHaveLength(STUDENT_CSV_TEMPLATE.headers.length)
    expect(
      parseStudentCsv([
        STUDENT_CSV_TEMPLATE.headers.join(','),
        STUDENT_CSV_TEMPLATE.sampleRow.join(',')
      ].join('\n')).valid
    ).toHaveLength(1)
  })
})
