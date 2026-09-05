import { describe, expect, it } from 'vitest'
import { MENTOR_CSV_TEMPLATE, parseMentorCsv } from '@/utils/adminMentorCsv'

const header = [
  'Email Address',
  'First Name',
  'Surname',
  'Country',
  'Region',
  'Mentor Reason',
  'Capacity',
  'Area(s) of Interest',
  'Background',
  'Institution or Company'
].join(',')

describe('parseMentorCsv', () => {
  it('parses a valid mentor registration export row', () => {
    const csv = [
      header,
      [
        'M.SOMERVILLE@EXAMPLE.EDU',
        'Mary',
        'Somerville',
        'Australia',
        'NSW',
        'I want to support students exploring biotech careers.',
        '2',
        '"Genetics, Bioinformatics, Genetics"',
        'Postgraduate',
        'University of Sydney'
      ].join(',')
    ].join('\n')

    const result = parseMentorCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid).toEqual([
      {
        firstName: 'Mary',
        lastName: 'Somerville',
        email: 'm.somerville@example.edu',
        country: 'Australia',
        state: 'NSW',
        interests: ['Genetics', 'Bioinformatics'],
        mentorReason: 'I want to support students exploring biotech careers.',
        mentorInstitution: 'University of Sydney',
        mentorBackground: 'postgraduate',
        mentorMaxGroupCount: 2,
        backgroundNote: undefined
      }
    ])
  })

  it('accepts aliases and maps supported mentor backgrounds', () => {
    const csv = [
      'email,firstname,lastname,country,state,mentor reason,max group count,interests,background,institution',
      'mentor@example.edu,Ada,Lovelace,Australia,VIC,Help students,3,"AI, AI, Ethics",HDR candidate,Lab One',
      'industry@example.edu,Grace,Hopper,United States,,Career guidance,1,Computing,Industry,Company One',
      'undergrad@example.edu,Alan,Turing,Australia,NSW,Share experience,2,Genetics,Undergraduate student,Uni Two'
    ].join('\n')

    const result = parseMentorCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid.map((row) => row.mentorBackground)).toEqual([
      'hdr',
      'industry',
      'undergraduate'
    ])
    expect(result.valid[0]).toMatchObject({
      email: 'mentor@example.edu',
      state: 'VIC',
      mentorMaxGroupCount: 3,
      interests: ['AI', 'Ethics']
    })
  })

  it('reports row-level validation problems without blocking valid rows', () => {
    const csv = [
      header,
      '',
      ',Missing,Email,Australia,NSW,,0,,Academic,',
      'not-an-email,Ada,Lovelace,Australia,NSW,Help students,2,Genetics,Academic,University',
      'valid@example.edu,Valid,Mentor,Australia,NSW,Help students,1,Genetics,Academic,University'
    ].join('\n')

    const result = parseMentorCsv(csv)

    expect(result.valid).toHaveLength(1)
    expect(result.valid[0]).toMatchObject({
      email: 'valid@example.edu',
      mentorBackground: null,
      backgroundNote: 'background "Academic" not recognised - left unset'
    })
    expect(result.invalid).toEqual([
      {
        rowNumber: 2,
        email: '(no email)',
        reason:
          'missing email, no interests, missing mentor reason, missing institution, invalid capacity'
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
      header,
      'country-as-region@example.edu,Case,One,Australia,Australia,Help students,2,Genetics,Industry,Company',
      'blank-region@example.edu,Case,Two,New Zealand,,Help students,2,Bioinformatics,Industry,Company'
    ].join('\n')

    const result = parseMentorCsv(csv)

    expect(result.invalid).toEqual([])
    expect(result.valid.map((row) => row.state)).toEqual([null, null])
  })

  it('throws a file-level error for an empty CSV', () => {
    expect(() => parseMentorCsv('')).toThrow('The CSV file is empty.')
  })

  it('throws a file-level error when required columns are missing', () => {
    expect(() => parseMentorCsv('Email,First Name\nmentor@example.edu,Ada')).toThrow(
      "This doesn't look like a Mentors export - missing columns: Surname, Country, Area(s) of Interest, Mentor Reason, Institution or Company, Capacity."
    )
  })

  it('exports the mentor CSV template with parser-compatible headers', () => {
    expect(MENTOR_CSV_TEMPLATE.fileName).toBe('mentor-import-template.csv')
    expect(MENTOR_CSV_TEMPLATE.headers).toEqual([
      'Email Address',
      'First Name',
      'Surname',
      'Country',
      'Region',
      'Mentor Reason',
      'Capacity',
      'Area(s) of Interest',
      'Background',
      'Institution or Company'
    ])
    expect(MENTOR_CSV_TEMPLATE.sampleRow).toHaveLength(MENTOR_CSV_TEMPLATE.headers.length)
    expect(
      parseMentorCsv([
        MENTOR_CSV_TEMPLATE.headers.join(','),
        MENTOR_CSV_TEMPLATE.sampleRow.join(',')
      ].join('\n')).valid
    ).toHaveLength(1)
  })
})
