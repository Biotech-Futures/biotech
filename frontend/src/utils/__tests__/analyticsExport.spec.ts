import { describe, expect, it } from 'vitest'
import {
  accountStatusLabel,
  activityStatusLabel,
  csvCell,
  daysSince,
  detailsCsv,
  exportFileName,
  figure,
  isoUtc,
  summaryCsv,
  toCsv,
} from '@/utils/analyticsExport'

describe('analytics CSV export', () => {
  it('quotes only when needed and neutralises spreadsheet formulas', () => {
    expect(csvCell('Sample group')).toBe('Sample group')
    expect(csvCell('Smith, Jo')).toBe('"Smith, Jo"')
    expect(csvCell('Say "hi"')).toBe('"Say ""hi"""')
    expect(csvCell('two\nlines')).toBe('"two\nlines"')
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`)
    expect(csvCell('+61 400')).toBe("'+61 400")
    expect(csvCell('@admin')).toBe("'@admin")
    expect(csvCell(-5)).toBe('-5')
    expect(csvCell(null)).toBe('')
    expect(csvCell(Number.NaN)).toBe('')
    expect(csvCell(true)).toBe('Yes')
  })

  it('writes UTF-8 with a byte order mark and CRLF line endings', () => {
    expect(toCsv([['a', 1], ['b', 2]])).toBe('﻿a,1\r\nb,2\r\n')
    expect(detailsCsv(['Name'], [['—']])).toBe('﻿Name\r\n—\r\n')
  })

  it('splits displayed figures into numbers and units', () => {
    expect(figure('S', 'M', '2,708')).toMatchObject({ value: 2708, unit: '' })
    expect(figure('S', 'M', '48%')).toMatchObject({ value: 48, unit: '%' })
    expect(figure('S', 'M', '—')).toMatchObject({ value: '', notes: 'Unavailable' })
    expect(figure('S', 'M', 'BTF153', '', 'Most active')).toMatchObject({ value: 'BTF153', notes: 'Most active' })
    expect(figure('S', 'M', 12, 'groups')).toMatchObject({ value: 12, unit: 'groups' })
  })

  it('opens summaries with rows that say what the file covers', () => {
    const csv = summaryCsv(
      { page: 'Groups', covers: 'Year 2026', filters: [['View', 'groups']], dataAsOf: '2026-10-15', unavailable: ['participant details'] },
      [figure('Groups', 'Total groups', 40, 'groups')],
    )
    const lines = csv.replace('﻿', '').trim().split('\r\n')
    expect(lines[0]).toBe('Section,Metric,Value,Unit,Notes')
    expect(lines).toContain('Report,Page,Groups Analytics,,')
    expect(lines).toContain('Report,Covers,Year 2026,,')
    expect(lines).toContain('Report,Filter: View,groups,,')
    expect(lines).toContain('Report,Data as of,2026-10-15,,Latest date with recorded data (UTC)')
    expect(lines.some((line) => /^Report,Generated at,\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z,UTC,$/.test(line))).toBe(true)
    expect(lines).toContain('Report,Unavailable data,participant details,,Could not be loaded; related figures are left out')
    expect(lines.at(-1)).toBe('Groups,Total groups,40,groups,')
  })

  it('names files by page, kind and scope', () => {
    expect(exportFileName('Email Monitoring', 'summary', '2026-09-01 to 2026-10-01')).toBe(
      'biotech-email-monitoring-summary-2026-09-01-to-2026-10-01.csv',
    )
    expect(exportFileName('users', 'details', '2026')).toBe('biotech-users-details-2026.csv')
  })

  it('formats times as ISO UTC and counts days to a reference day', () => {
    expect(isoUtc('2026-10-15T09:16:30.123Z')).toBe('2026-10-15T09:16:30Z')
    expect(isoUtc('not a date')).toBe('')
    expect(isoUtc(null)).toBe('')
    const asOf = new Date('2026-10-15T00:00:00Z')
    expect(daysSince('2026-10-01T12:00:00Z', asOf)).toBe(13)
    expect(daysSince(null, asOf)).toBeNull()
  })

  it('keeps login recency separate from account status', () => {
    expect(activityStatusLabel(0)).toBe('Active')
    expect(activityStatusLabel(13)).toBe('Active')
    expect(activityStatusLabel(14)).toBe('Inactive')
    expect(activityStatusLabel(null)).toBe('Never logged in')
    expect(accountStatusLabel('deactivated')).toBe('Deactivated')
    expect(accountStatusLabel(null, true)).toBe('Active')
    expect(accountStatusLabel('', false)).toBe('Deactivated')
    expect(accountStatusLabel(undefined)).toBe('')
  })
})
