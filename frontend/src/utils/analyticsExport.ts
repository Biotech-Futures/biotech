/**
 * CSV exports shared by every Analytics page.
 *
 * Each page offers files built from the data it is showing:
 * - Summary: one row per figure (Section, Metric, Value, Unit, Notes). It opens
 *   with "Report" rows saying what the file covers, and values are plain
 *   numbers with the unit in its own column, so the file can be filtered,
 *   pivoted or charted without cleaning.
 * - Details: one header row and one row per record, following the page's
 *   filters. Dates are ISO 8601 in UTC and missing values are empty cells.
 *
 * Files are UTF-8 with a byte order mark and CRLF line endings so Excel opens
 * them correctly, and text a spreadsheet would run as a formula is neutralised.
 */

import type { AnalyticsSource } from '@/utils/liveAnalyticsData'

export type CsvCell = string | number | boolean | null | undefined

export const ANALYTICS_SOURCE_LABELS: Record<AnalyticsSource, string> = {
  users: 'participant details',
  groups: 'group details',
  mentors: 'mentor details',
  groupActivity: 'message activity',
  loginActivity: 'login history',
  resourceAnalytics: 'resource activity',
  emailAnalytics: 'email delivery',
  resources: 'resource catalogue',
}

export const sourceLabels = (sources: AnalyticsSource[]) => sources.map((source) => ANALYTICS_SOURCE_LABELS[source])

/** 'summary', 'details', or a page-specific list such as 'unassigned'. */
export type ExportKind = string

export interface ExportOption {
  kind: ExportKind
  label: string
  description: string
  disabled?: boolean
}

export interface SummaryRow {
  section: string
  metric: string
  value: CsvCell
  unit?: string
  notes?: string
}

export interface ReportInfo {
  /** Page name, e.g. "Users". */
  page: string
  /** What the figures cover, e.g. "Year 2026" or "2026-09-01 to 2026-10-01 (UTC)". */
  covers: string
  /** Filters applied on the page, as [name, value] pairs. */
  filters?: Array<[string, CsvCell]>
  /** Latest date with recorded data (YYYY-MM-DD), when the page uses one. */
  dataAsOf?: string | null
  /** Data sources that could not be loaded; their figures are left out. */
  unavailable?: string[]
}

export const EXPORT_ERROR_MESSAGE = 'The CSV could not be created. Refresh the page and try again.'

// A leading =, +, -, @, tab or carriage return makes spreadsheets evaluate text
// as a formula, so names typed by users could run in Excel when opened.
const FORMULA_PREFIX = /^[=+\-@\t\r]/

export function csvCell(value: CsvCell): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  let text = String(value)
  if (FORMULA_PREFIX.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) || text !== text.trim() ? `"${text.replace(/"/g, '""')}"` : text
}

export function toCsv(rows: CsvCell[][]): string {
  return `﻿${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}\r\n`
}

/** An ISO 8601 UTC timestamp without milliseconds, or '' when there is no valid date. */
export function isoUtc(value: string | Date | null | undefined): string {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/** The YYYY-MM-DD part of a date, or '' when there is none. */
export function isoDay(value: string | Date | null | undefined): string {
  return isoUtc(value).slice(0, 10)
}

/** Whole days from a timestamp to a reference day, or null when there is no timestamp. */
export function daysSince(value: string | null | undefined, asOf: Date): number | null {
  if (!value) return null
  const time = new Date(value).getTime()
  if (Number.isNaN(time)) return null
  return Math.max(0, Math.floor((asOf.getTime() - time) / 86_400_000))
}

/** A login within this many days counts as active on every Analytics page (client feedback F04). */
export const ACTIVE_WINDOW_DAYS = 14

export type ActivityStatusLabel = 'Active' | 'Inactive' | 'Never logged in'

/** Login recency only; account status is reported separately. */
export function activityStatusLabel(daysSinceLogin: number | null | undefined): ActivityStatusLabel {
  if (daysSinceLogin === null || daysSinceLogin === undefined) return 'Never logged in'
  return daysSinceLogin < ACTIVE_WINDOW_DAYS ? 'Active' : 'Inactive'
}

/** "deactivated" → "Deactivated"; falls back to the is_active flag when no status is sent. */
export function accountStatusLabel(status: string | null | undefined, isActive?: boolean): string {
  const text = (status ?? '').trim()
  if (text) return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()
  if (isActive === undefined) return ''
  return isActive ? 'Active' : 'Deactivated'
}

export function percentOf(part: number, total: number, places = 1): number | null {
  if (!total) return null
  const factor = 10 ** places
  return Math.round((part / total) * 100 * factor) / factor
}

const DISPLAY_NUMBER = /^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$/
const MISSING = new Set(['', '—', '-', 'N/A', 'Unavailable'])

/**
 * A summary row from a figure as the page displays it: "2,708" becomes 2708,
 * "48%" becomes 48 with unit "%", and "—" becomes an empty value.
 */
export function figure(section: string, metric: string, value: CsvCell, unit = '', notes = ''): SummaryRow {
  if (typeof value === 'string') {
    const text = value.trim()
    if (MISSING.has(text)) return { section, metric, value: '', unit, notes: notes || 'Unavailable' }
    const percent = text.endsWith('%') ? text.slice(0, -1).trim() : null
    const numeric = percent ?? text
    if (DISPLAY_NUMBER.test(numeric)) {
      return { section, metric, value: Number(numeric.replace(/,/g, '')), unit: percent !== null ? '%' : unit, notes }
    }
  }
  return { section, metric, value, unit, notes }
}

export function summaryCsv(info: ReportInfo, rows: SummaryRow[]): string {
  const report: SummaryRow[] = [
    { section: 'Report', metric: 'Page', value: `${info.page} Analytics` },
    { section: 'Report', metric: 'Covers', value: info.covers },
    ...(info.filters ?? []).map(([name, value]) => ({ section: 'Report', metric: `Filter: ${name}`, value })),
    ...(info.dataAsOf ? [{ section: 'Report', metric: 'Data as of', value: info.dataAsOf, notes: 'Latest date with recorded data (UTC)' }] : []),
    { section: 'Report', metric: 'Generated at', value: isoUtc(new Date()), unit: 'UTC' },
    ...(info.unavailable?.length
      ? [{ section: 'Report', metric: 'Unavailable data', value: info.unavailable.join('; '), notes: 'Could not be loaded; related figures are left out' }]
      : []),
  ]
  return toCsv([
    ['Section', 'Metric', 'Value', 'Unit', 'Notes'],
    ...[...report, ...rows].map((row) => [row.section, row.metric, row.value, row.unit ?? '', row.notes ?? '']),
  ])
}

export function detailsCsv(headers: string[], rows: CsvCell[][]): string {
  return toCsv([headers, ...rows])
}

const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')

/** biotech-{page}-{summary|details}-{scope}.csv, e.g. biotech-users-details-2026.csv */
export function exportFileName(page: string, kind: ExportKind, scope: string): string {
  return `biotech-${[slug(page), kind, slug(scope)].filter(Boolean).join('-')}.csv`
}

export function downloadCsv(fileName: string, csv: string) {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Runs an export; returns '' on success or a message to show the admin. */
export function runExport(build: () => { fileName: string; csv: string }): string {
  try {
    const { fileName, csv } = build()
    downloadCsv(fileName, csv)
    return ''
  } catch (error) {
    console.error('Analytics export failed.', error)
    return EXPORT_ERROR_MESSAGE
  }
}

export const SUMMARY_OPTION: ExportOption = {
  kind: 'summary',
  label: 'Summary',
  description: 'Every figure and chart on this page',
}

export const DETAILS_OPTION: ExportOption = {
  kind: 'details',
  label: 'Details',
  description: 'One row per record, with the current filters',
}
